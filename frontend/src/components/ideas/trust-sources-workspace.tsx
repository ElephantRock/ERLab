/**
 * Phase 2 2C: Trust & Sources workspace.
 *
 * Renders the normalized review payload (Phase 2 2B) for a paper: separate
 * statuses for paper evaluation, proposal evaluation, citation audit, and
 * human source review; a filterable/searchable source list; per-source detail;
 * and human review decisions (2E/2F).
 *
 * Truth rules (WP-2B/2C):
 *  - automated and human review statuses are distinct (never collapsed)
 *  - missing confidence/metadata shown as unavailable, never fabricated
 *  - proposal and paper evaluations remain distinct
 *  - section-to-source mapping shown where supported; unavailable stated explicitly
 *  - a review decision does NOT mutate the existing paper (immutability rule)
 *  - no aggregate trust score
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  ExternalLink,
  Search,
  Loader2,
  Ban,
  Flag,
} from "lucide-react";
import { toast } from "sonner";
import { getReview, recordSourceDecision } from "@/api/review";
import type { ReviewSource, SourceReviewDecisionRequest } from "@/api/types";

type Filter = "all" | "resolved" | "unresolved" | "flagged" | "unreviewed";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "resolved", label: "Resolved" },
  { value: "unresolved", label: "Unresolved" },
  { value: "flagged", label: "Flagged / Excluded" },
  { value: "unreviewed", label: "Unreviewed" },
];

const DECISIONS: { value: SourceReviewDecisionRequest["decision"]; label: string; icon: typeof Flag }[] = [
  { value: "accepted", label: "Accept", icon: CheckCircle2 },
  { value: "flagged", label: "Flag", icon: Flag },
  { value: "exclude_on_next_revision", label: "Exclude next", icon: Ban },
];

interface TrustSourcesWorkspaceProps {
  ideaId: number;
}

export function TrustSourcesWorkspace({ ideaId }: TrustSourcesWorkspaceProps) {
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [selectedHash, setSelectedHash] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["review", ideaId],
    queryFn: () => getReview(ideaId),
  });

  const decisionMutation = useMutation({
    mutationFn: (req: SourceReviewDecisionRequest) => recordSourceDecision(ideaId, req),
    onSuccess: () => {
      toast.success("Review decision recorded");
      // Invalidate the review payload so the source list + summary refresh.
      queryClient.invalidateQueries({ queryKey: ["review", ideaId] });
    },
    onError: () => toast.error("Failed to record decision"),
  });

  const sources = data?.sources ?? [];
  const human = data?.human_review;
  const checks = data?.automated_checks;

  const filteredSources = useMemo(() => {
    const q = search.trim().toLowerCase();
    return sources.filter((s) => {
      if (q) {
        const hay = `${s.raw} ${s.title ?? ""} ${s.authors ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      switch (filter) {
        case "resolved":
          return s.resolution_status === "resolved";
        case "unresolved":
          return s.resolution_status === "unresolved";
        case "flagged":
          return (
            s.human_decision?.decision === "flagged" ||
            s.human_decision?.decision === "exclude_on_next_revision"
          );
        case "unreviewed":
          return s.human_decision === null;
        default:
          return true;
      }
    });
  }, [sources, filter, search]);

  const selected = selectedHash ? sources.find((s) => s.source_ref_hash === selectedHash) ?? null : null;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading trust & sources…
      </div>
    );
  }
  if (isError) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-destructive">
          <AlertCircle className="mx-auto mb-3 h-8 w-8" />
          <p className="text-sm font-medium">Review data unavailable.</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {error instanceof Error ? error.message : "The review payload could not be loaded."}
          </p>
        </CardContent>
      </Card>
    );
  }
  if (!data) return null;

  return (
    <div className="space-y-5">
      {/* ── Summary: separate statuses, never collapsed ── */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatusCard
          label="Paper Evaluation"
          status={checks?.paper_evaluation?.status === "ready" ? "ready" : "unavailable"}
          detail={checks?.paper_evaluation?.status === "ready" ? "scope: paper" : undefined}
        />
        <StatusCard
          label="Proposal Evaluation"
          status={checks?.proposal_evaluation && "dimensions" in (checks.proposal_evaluation ?? {}) ? "ready" : "unavailable"}
          detail={checks?.proposal_evaluation ? "scope: proposal" : undefined}
        />
        <StatusCard
          label="Citation Audit"
          status="info"
          detail={`${sources.filter((s) => s.resolution_status === "resolved").length}/${sources.length} resolved`}
        />
        <StatusCard
          label="Human Source Review"
          status={human?.status === "completed" ? "ready" : human?.status === "completed_with_flags" ? "warning" : human?.status === "in_progress" ? "info" : "unavailable"}
          detail={human ? `${human.reviewed_sources}/${human.reviewable_sources} reviewed` : undefined}
        />
      </div>

      {/* ── Filter + search ── */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-1">
          {FILTERS.map((f) => (
            <Button
              key={f.value}
              size="sm"
              variant={filter === f.value ? "default" : "outline"}
              onClick={() => setFilter(f.value)}
            >
              {f.label}
            </Button>
          ))}
        </div>
        <div className="relative ml-auto">
          <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search sources…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-9 w-56 pl-8"
          />
        </div>
      </div>

      {/* ── Source list ── */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">
            Sources ({filteredSources.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          {filteredSources.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No sources match this filter.
            </p>
          ) : (
            filteredSources.map((s) => (
              <SourceRow
                key={s.source_ref_hash}
                source={s}
                selected={selectedHash === s.source_ref_hash}
                onSelect={() => setSelectedHash(s.source_ref_hash)}
              />
            ))
          )}
        </CardContent>
      </Card>

      {/* ── Source detail ── */}
      {selected && (
        <SourceDetail
          source={selected}
          onDecide={(decision) =>
            decisionMutation.mutate({
              source_ref_hash: selected.source_ref_hash,
              source_ref_number: selected.ref_number,
              decision,
            })
          }
          busy={decisionMutation.isPending}
        />
      )}

      {/* ── Regeneration boundary (2E) ── */}
      {!data.regeneration_available && human && human.flagged_or_excluded > 0 && (
        <p className="text-xs text-muted-foreground">
          Regeneration excluding flagged/excluded sources is not yet available.
          Your exclusion decisions are recorded for a future revision and do not
          change the current paper.
        </p>
      )}
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────

function StatusCard({
  label,
  status,
  detail,
}: {
  label: string;
  status: "ready" | "unavailable" | "warning" | "info";
  detail?: string;
}) {
  const tone =
    status === "ready"
      ? "text-success"
      : status === "warning"
        ? "text-warning"
        : status === "info"
          ? "text-info"
          : "text-muted-foreground";
  const Icon =
    status === "ready" ? CheckCircle2 : status === "warning" ? AlertTriangle : status === "info" ? AlertCircle : AlertCircle;
  return (
    <Card>
      <CardContent className="py-3">
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 ${tone}`} />
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {label}
          </span>
        </div>
        <p className={`mt-1 text-sm ${tone}`}>
          {status === "ready" ? "Ready" : status === "warning" ? "Has flags" : status === "info" ? "In progress" : "Unavailable"}
        </p>
        {detail && <p className="text-xs text-muted-foreground">{detail}</p>}
      </CardContent>
    </Card>
  );
}

function SourceRow({
  source,
  selected,
  onSelect,
}: {
  source: ReviewSource;
  selected: boolean;
  onSelect: () => void;
}) {
  const decision = source.human_decision?.decision;
  const decisionTone =
    decision === "accepted"
      ? "text-success"
      : decision === "flagged"
        ? "text-warning"
        : decision === "exclude_on_next_revision"
          ? "text-destructive"
          : null;
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`flex w-full items-center gap-3 rounded-md border px-3 py-2 text-left transition-colors hover:bg-muted/50 ${
        selected ? "border-primary bg-primary/5" : "border-border"
      }`}
    >
      <span className="w-12 shrink-0 font-mono text-xs text-muted-foreground">
        {source.citation_marker ?? "—"}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm">
          {source.title ?? source.raw.slice(0, 80) ?? "Untitled source"}
        </span>
        <span className="block truncate text-xs text-muted-foreground">
          {source.authors ? `${source.authors} ` : ""}
          {source.year ? `(${source.year}) ` : ""}
          {source.resolution_status === "unresolved" && (
            <span className="text-warning">unresolved</span>
          )}
          {source.match_method && (
            <span className="ml-1">· match: {source.match_method}</span>
          )}
        </span>
      </span>
      {decision && (
        <Badge variant="outline" className={`shrink-0 ${decisionTone ?? ""}`}>
          {decision === "exclude_on_next_revision" ? "excluded" : decision}
        </Badge>
      )}
    </button>
  );
}

function SourceDetail({
  source,
  onDecide,
  busy,
}: {
  source: ReviewSource;
  onDecide: (decision: SourceReviewDecisionRequest["decision"]) => void;
  busy: boolean;
}) {
  const Meta = ({ label, value }: { label: string; value: React.ReactNode }) => (
    <div className="flex gap-2 py-0.5">
      <span className="w-32 shrink-0 text-xs font-medium text-muted-foreground">{label}</span>
      <span className="text-xs">{value ?? <em className="text-muted-foreground">unavailable</em>}</span>
    </div>
  );

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          Source Detail
          {source.citation_marker && <Badge variant="outline" className="font-mono">{source.citation_marker}</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="rounded-md border p-3">
          <Meta label="Title" value={source.title ?? source.raw} />
          <Meta label="Authors" value={source.authors} />
          <Meta label="Year" value={source.year} />
          <Meta label="Venue" value={source.venue} />
          <Meta
            label="URL"
            value={
              source.url ? (
                <a href={source.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
                  {source.url} <ExternalLink className="h-3 w-3" />
                </a>
              ) : null
            }
          />
          <Meta label="DOI" value={source.doi} />
          <Meta
            label="Resolution"
            value={
              source.resolution_status === "resolved" ? (
                <span className="text-success">resolved</span>
              ) : (
                <span className="text-warning">unresolved</span>
              )
            }
          />
          <Meta label="Match method" value={source.match_method} />
          <Meta
            label="Confidence"
            value={
              source.confidence != null ? (
                <span>{(source.confidence * 100).toFixed(0)}%</span>
              ) : null
            }
          />
          <Meta
            label="Sections citing"
            value={
              source.sections_used.length > 0 ? (
                <span>{source.sections_used.join(", ")}</span>
              ) : (
                <em className="text-muted-foreground">unavailable (no persisted marker mapping)</em>
              )
            }
          />
        </div>

        {/* Existing decision */}
        {source.human_decision && (
          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs">
            <span className="font-medium">Current review:</span>{" "}
            <Badge variant="outline">{source.human_decision.decision}</Badge>
            {source.human_decision.note && <span className="ml-2">{source.human_decision.note}</span>}
            <span className="ml-2 text-muted-foreground">
              by {source.human_decision.reviewer} on{" "}
              {source.human_decision.reviewed_at
                ? new Date(source.human_decision.reviewed_at).toLocaleString()
                : "—"}
            </span>
          </div>
        )}

        {/* Decision controls (2E) — immutability: does not change the paper */}
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Review this source (does not change the current paper):
          </p>
          <div className="flex flex-wrap gap-2">
            {DECISIONS.map((d) => (
              <Button
                key={d.value}
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() => onDecide(d.value)}
              >
                <d.icon className="mr-1.5 h-3.5 w-3.5" />
                {d.label}
              </Button>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
