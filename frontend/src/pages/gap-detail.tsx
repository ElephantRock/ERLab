import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { getGap, updateGapStatus, asGapStatus, type GapStatus } from "@/api/gaps";
import { getGapPapers } from "@/api/clients/gap-papers-client";
import { parseRouteId } from "@/lib/route-ids";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, ArrowRight, BookOpen, GitBranch, Lightbulb, BarChart3, FileText, Loader2, AlertCircle } from "lucide-react";
import { GapFeedbackForm } from "@/components/gaps/gap-feedback-form";
import type { ResearchGap, RelatedIdea, MatchedPaper } from "@/api/types";

/** Gap type badge color mapping. */
const GAP_TYPE_COLORS: Record<string, string> = {
  methodological: "bg-info/10 text-info",
  empirical: "bg-success/10 text-success",
  theoretical: "bg-info/10 text-info",
  "cross-domain": "bg-warning/10 text-warning",
};

// ── Route wrapper: validates ID before any hooks that fetch ──────────

export default function GapDetailPage() {
  const { id } = useParams<{ id: string }>();
  const parsed = parseRouteId(id);

  if (parsed.kind !== "valid") {
    return <InvalidRouteId entity="gap" raw={parsed.kind === "invalid" ? parsed.raw : undefined} />;
  }

  return <GapDetailContent gapId={parsed.value} />;
}

// ── Invalid route-ID state (zero requests) ───────────────────────────

function InvalidRouteId({ entity, raw }: { entity: string; raw?: string }) {
  const navigate = useNavigate();
  return (
    <div className="space-y-4 text-center py-12">
      <AlertCircle className="h-12 w-12 mx-auto text-destructive opacity-50" />
      <h2 className="text-xl font-semibold">Invalid {entity} ID</h2>
      <p className="text-muted-foreground">
        {raw !== undefined
          ? `The URL parameter "${raw}" is not a valid ${entity} identifier.`
          : `No ${entity} ID was provided in the URL.`}
      </p>
      <Button variant="outline" onClick={() => navigate("/gaps")}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Gaps Explorer
      </Button>
    </div>
  );
}

// ── Content component: receives a guaranteed valid positive integer ──

function GapDetailContent({ gapId }: { gapId: number }) {
  const navigate = useNavigate();
  const [papersExpanded, setPapersExpanded] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["gap", gapId],
    queryFn: () => getGap(gapId),
  });

  // Lazy gap-papers expansion — only fetched when user activates it
  const papersQuery = useQuery({
    queryKey: ["gap-papers", gapId],
    queryFn: () => getGapPapers(gapId),
    enabled: papersExpanded,
  });

  // F1.4.2 + F1.5c: gap status mutation.
  // - retry: false (non-idempotent PATCH)
  // - meta.invalidateQueries: cache-owned invalidation that fires whether
  //   or not this component is still mounted. Without this, navigating away
  //   mid-PATCH would silently lose the invalidation and leave the cache
  //   stale relative to backend truth.
  // - onError: component-level toast (UX feedback only)
  const statusMutation = useMutation({
    mutationFn: (status: GapStatus) => updateGapStatus(gapId, status),
    retry: false,
    mutationKey: ["gap", gapId, "status"],
    meta: {
      invalidateQueries: [["gap", gapId]],
    },
    onError: () => {
      toast.error("Failed to update gap status");
    },
  });

  const gap: ResearchGap | undefined = data?.gap;
  const relatedIdeas: RelatedIdea[] | null = gap?.related_ideas ?? null;
  const previewPapers: MatchedPaper[] | null = gap?.matched_papers_preview ?? null;

  // Use expanded endpoint results when available, otherwise the preview
  const displayPapers: MatchedPaper[] | null = papersQuery.data?.papers ?? null;
  const papersTotal: number | null = papersQuery.data?.total ?? null;

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-10 w-3/4" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (isError || !gap) {
    return (
      <div className="space-y-4 text-center py-12">
        <GitBranch className="h-12 w-12 mx-auto text-muted-foreground opacity-50" />
        <h2 className="text-xl font-semibold">Gap not found</h2>
        <p className="text-muted-foreground">
          The research gap with ID {gapId} could not be found.
        </p>
        <Button variant="outline" onClick={() => navigate("/gaps")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Gaps Explorer
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/gaps")}
          className="mb-2"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Back to Gaps
        </Button>
        <h1 className="text-2xl font-bold tracking-tight">{gap.title}</h1>
        <div className="flex items-center gap-3 mt-2">
          <span
            className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
              GAP_TYPE_COLORS[gap.gap_type] || "bg-muted/50 text-muted-foreground"
            }`}
          >
            {gap.gap_type || "unknown"}
          </span>
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
            <div className="w-32 bg-muted/50 rounded-full h-2">
              <div
                className="bg-primary rounded-full h-2 transition-[width]"
                style={{ width: `${Math.round(gap.confidence * 100)}%` }}
              />
            </div>
            <span className="text-sm text-muted-foreground">
              {Math.round(gap.confidence * 100)}% confidence
            </span>
          </div>
          <select
            value={gap.status || "identified"}
            onChange={(e) => {
              const next = asGapStatus(e.target.value);
              if (!next) return;
              if (next === gap.status) return;
              if (statusMutation.isPending) return;
              statusMutation.mutate(next);
            }}
            disabled={statusMutation.isPending}
            className="px-2 py-0.5 text-xs border rounded-md bg-background disabled:opacity-50"
            aria-label="Gap lifecycle status"
            data-testid="gap-status-select"
          >
            <option value="identified">Identified</option>
            <option value="investigating">Investigating</option>
            <option value="addressed">Addressed</option>
          </select>
          {statusMutation.isPending && (
            <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" data-testid="status-pending" />
          )}
        </div>
      </div>

      {/* Description */}
      <div className="bg-card border rounded-lg p-4">
        <h2 className="text-lg font-semibold mb-2">Description</h2>
        <p className="text-muted-foreground whitespace-pre-wrap">
          {gap.description || "No description available."}
        </p>
        {gap.potential_impact && (
          <div className="mt-4 pt-4 border-t">
            <h3 className="text-sm font-medium mb-1">Potential Impact</h3>
            <p className="text-sm text-muted-foreground">{gap.potential_impact}</p>
          </div>
        )}
      </div>

      {/* Truth Values */}
      {gap.truth && (
        <div className="bg-card border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <BookOpen className="h-5 w-5" />
            Truth Values
          </h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-muted-foreground">Frequency</p>
              <p className="text-lg font-medium">{parseFloat(String(gap.truth.frequency)).toFixed(3)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Confidence</p>
              <p className="text-lg font-medium">{parseFloat(String(gap.truth.confidence)).toFixed(3)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Evidence Count</p>
              <p className="text-lg font-medium">{gap.truth.evidence_count}</p>
            </div>
          </div>
        </div>
      )}

      {/* Cluster Membership */}
      {gap.related_clusters && gap.related_clusters.length > 0 && (
        <div className="bg-card border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <GitBranch className="h-5 w-5" />
            Cluster Membership
          </h2>
          <div className="flex flex-wrap gap-2">
            {gap.related_clusters.map((clusterId) => (
              <span
                key={clusterId}
                className="px-3 py-1 bg-muted rounded-full text-sm font-medium"
              >
                Cluster {clusterId}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Related Ideas */}
      {relatedIdeas && relatedIdeas.length > 0 && (
        <div className="bg-card border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <Lightbulb className="h-5 w-5" />
            Related Ideas
          </h2>
          <ul className="space-y-2">
            {relatedIdeas.map((idea) => (
              <li key={idea.id}>
                <button
                  type="button"
                  role="link"
                  onClick={() => navigate(`/ideas/${idea.id}`)}
                  className="flex items-center gap-2 text-sm hover:text-primary text-left w-full"
                  data-testid={`related-idea-${idea.id}`}
                >
                  <ArrowRight className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                  <span className="truncate">{idea.title}</span>
                  {idea.overall_score != null && (
                    <span className="text-xs text-muted-foreground ml-auto">
                      {idea.overall_score.toFixed(2)}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Matched Papers */}
      {previewPapers && previewPapers.length > 0 && (
        <div className="bg-card border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Matched Papers
          </h2>
          <p className="text-xs text-muted-foreground mb-3">
            Papers matched by keyword overlap. Not a guaranteed provenance link.
          </p>

          {/* Render expanded results if loaded, otherwise the preview */}
          {papersExpanded && papersQuery.isLoading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading more matched papers...
            </div>
          )}

          {papersExpanded && papersQuery.isError && (
            <div className="text-sm text-destructive py-2 flex items-center justify-between">
              <span>Failed to load papers.</span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => papersQuery.refetch()}
              >
                Retry
              </Button>
            </div>
          )}

          {/* Papers list: expanded endpoint results when available, preview otherwise */}
          <ul className="space-y-2">
            {(displayPapers ?? previewPapers).map((paper) => (
              <li key={paper.id} className="text-sm border-l-2 border-muted pl-3">
                <p className="font-medium">{paper.title}</p>
                <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
                  {paper.year && <span>{paper.year}</span>}
                  {paper.venue && <span>{paper.venue}</span>}
                  {paper.citation_count != null && (
                    <span>{paper.citation_count} citations</span>
                  )}
                </div>
                {paper.abstract && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {paper.abstract}
                  </p>
                )}
              </li>
            ))}
          </ul>

          {/* Truthful coverage label when expanded */}
          {papersExpanded && !papersQuery.isLoading && !papersQuery.isError && displayPapers && papersTotal !== null && (
            <p className="text-xs text-muted-foreground mt-2">
              {displayPapers.length === papersTotal
                ? `Showing all ${papersTotal} matched papers`
                : `Showing ${displayPapers.length} of ${papersTotal} matched papers`}
            </p>
          )}

          {/* Expansion toggle: only shown before first expansion */}
          {!papersExpanded && (
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={() => setPapersExpanded(true)}
            >
              Show more matched papers
            </Button>
          )}

          {/* Successful empty from endpoint */}
          {papersExpanded && !papersQuery.isLoading && !papersQuery.isError && displayPapers && displayPapers.length === 0 && (
            <p className="text-xs text-muted-foreground mt-2">
              No additional matched papers found.
            </p>
          )}
        </div>
      )}

      {/* Metadata */}
      <div className="text-xs text-muted-foreground">
        <p>Gap ID: {gap.id}</p>
        {gap.pipeline_run_id && <p>Pipeline Run: {gap.pipeline_run_id}</p>}
      </div>

      {/* Feedback Form */}
      <div className="bg-card border rounded-lg p-4">
        <GapFeedbackForm
          gapId={gap.id}
          currentRating={gap.user_rating}
          currentNotes={gap.user_notes}
        />
      </div>
    </div>
  );
}
