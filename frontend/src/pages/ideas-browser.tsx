/**
 * Ideas Browser — Triage Surface.
 *
 * PRODUCT.md §5: "Density serves the step." TRIAGE may be dense — the
 * researcher is scanning. This page is dense by design; the reading surface
 * (idea-detail) is where density yields to breath.
 *
 * INTERFACE_CONTRACT compliance:
 * - §1 useResource + DataView (not raw useQuery)
 * - §3 ui-scale typography (no sub-micro)
 * - §6 ScoreReport compact for triage scannability
 */

import { useState, useMemo } from "react";
import { useResource } from "@/lib/useResource";
import { DataView } from "@/components/ui/data-view";
import { listIdeas } from "@/api/ideas";
import { ScoreReport } from "@/components/ui/score-report";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { useNavigate } from "react-router-dom";
import {
  Search, ChevronLeft, ChevronRight, Play, Inbox, SlidersHorizontal,
  ChevronRight as Chevron,
} from "lucide-react";

const SORT_OPTIONS = [
  { value: "date", label: "Newest First" },
  { value: "score", label: "Overall Score" },
  { value: "novelty", label: "Novelty Score" },
  { value: "feasibility", label: "Feasibility Score" },
] as const;

export default function IdeasBrowser() {
  const navigate = useNavigate();
  const [searchText, setSearchText] = useState("");
  const [domainFilter, setDomainFilter] = useState("");
  const [sortBy, setSortBy] = useState("date");
  const [minScore, setMinScore] = useState(0);
  const [page, setPage] = useState(0);
  const [showFilters, setShowFilters] = useState(false);
  const limit = 20;

  const queryParams = useMemo(
    () => ({
      domain: domainFilter || undefined,
      search: searchText || undefined,
      sort_by: sortBy !== "date" ? sortBy : undefined,
      min_score: minScore > 0 ? minScore : undefined,
      limit,
      offset: page * limit,
    }),
    [domainFilter, searchText, sortBy, minScore, page, limit],
  );

  // INTERFACE_CONTRACT §1: useResource is the only sanctioned fetch hook.
  const resource = useResource(
    ["ideas", queryParams],
    () => listIdeas(queryParams),
  );

  const total = resource.status === "ready" ? resource.data.total : 0;

  return (
    <div className="space-y-5 animate-fade-in" data-testid="ideas-browser">
      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Inbox className="h-5 w-5 text-accent" />
            <h1 className="text-ui-display font-display font-semibold tracking-tight">
              Results
            </h1>
          </div>
          <p className="text-ui-meta text-muted-foreground">
            {total > 0 ? `${total} research ideas generated from your pipeline runs.` : "Research ideas from pipeline runs."}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => navigate("/pipeline/new")}>
          <Play className="mr-2 h-3.5 w-3.5" />
          New Run
        </Button>
      </div>

      {/* ── Search + Filters ── */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search ideas by title..."
            value={searchText}
            onChange={(e) => { setSearchText(e.target.value); setPage(0); }}
            className="pl-9"
            aria-label="Search ideas by title"
          />
        </div>
        <Button
          variant={showFilters ? "default" : "outline"}
          size="sm"
          onClick={() => setShowFilters(!showFilters)}
          className="flex-shrink-0"
        >
          <SlidersHorizontal className="mr-1.5 h-3.5 w-3.5" />
          Filters
        </Button>
      </div>

      {/* ── Expandable filter panel ── */}
      {showFilters && (
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end rounded-lg border border-border bg-card p-4 animate-fade-in">
          <div className="w-full sm:w-[180px]">
            <label className="text-ui-meta text-muted-foreground mb-1 block">Sort by</label>
            <Select value={sortBy} onValueChange={(v) => { setSortBy(v); setPage(0); }}>
              <SelectTrigger aria-label="Sort ideas by"><SelectValue /></SelectTrigger>
              <SelectContent>
                {SORT_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex-1">
            <label className="text-ui-meta text-muted-foreground mb-1 block">
              Min Score: {minScore.toFixed(1)}
            </label>
            <Slider
              value={[minScore]}
              onValueChange={(v) => { setMinScore(v[0] ?? 0); setPage(0); }}
              min={0} max={1} step={0.1}
              aria-label="Minimum overall score filter"
            />
          </div>
          <div className="w-full sm:w-[180px]">
            <label className="text-ui-meta text-muted-foreground mb-1 block">Domain</label>
            <Input
              placeholder="Filter by domain..."
              value={domainFilter}
              onChange={(e) => { setDomainFilter(e.target.value); setPage(0); }}
              aria-label="Filter by domain"
            />
          </div>
        </div>
      )}

      {/* ── Results via DataView ── */}
      <DataView
        resource={resource}
        testId="ideas"
        empty={{
          what: "ideas",
          icon: Search,
          title: searchText || domainFilter ? "No ideas match your filters" : "No research ideas yet",
          message: searchText || domainFilter ? "Try adjusting your search or filters." : "Run the pipeline to generate ideas from literature.",
          action: !searchText && !domainFilter ? (
            <Button onClick={() => navigate("/pipeline/new")}>
              <Play className="mr-2 h-4 w-4" />
              Start New Research Run
            </Button>
          ) : (
            <Button variant="outline" onClick={() => { setSearchText(""); setDomainFilter(""); setMinScore(0); }}>
              Clear Filters
            </Button>
          ),
        }}
      >
        {(data) => (
          <>
            <div className="grid gap-3 md:grid-cols-2">
              {data.ideas.map((idea) => (
                <TriageCard
                  key={idea.id}
                  idea={idea}
                  onClick={() => navigate(`/ideas/${idea.id}`)}
                />
              ))}
            </div>

            {/* ── Pagination ── */}
            {data.total > limit && (
              <div className="flex items-center justify-between pt-4">
                <Button
                  variant="outline" size="sm"
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <ChevronLeft className="mr-1 h-4 w-4" />
                  Previous
                </Button>
                <span className="text-ui-meta text-muted-foreground">
                  Page {page + 1} of {Math.ceil(data.total / limit)}
                </span>
                <Button
                  variant="outline" size="sm"
                  disabled={(page + 1) * limit >= data.total}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                  <ChevronRight className="ml-1 h-4 w-4" />
                </Button>
              </div>
            )}
          </>
        )}
      </DataView>
    </div>
  );
}

// ── Triage Card — dense, scannable, ScoreReport compact ──────────

function TriageCard({
  idea,
  onClick,
}: {
  idea: {
    id: number;
    title: string;
    domain: string;
    novelty_score: number | null;
    feasibility_score: number | null;
    overall_score: number | null;
    has_proposal: boolean;
    quality_summary?: { has_issues?: boolean } | null;
  };
  onClick: () => void;
}) {
  return (
    <div
      className="rounded-lg border border-border bg-card card-shadow card-shadow-hover transition-all cursor-pointer p-4"
      onClick={onClick}
      role="button"
      tabIndex={0}
      data-testid={`idea-card-${idea.id}`}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } }}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="text-ui-label font-medium leading-snug line-clamp-2 flex-1 hover:text-accent transition-colors">
          {idea.title}
        </h3>
        {idea.quality_summary?.has_issues && (
          <span className="text-ui-micro bg-warning/10 text-warning px-1.5 py-0.5 rounded font-medium shrink-0">
            issues
          </span>
        )}
      </div>

      <div className="flex items-center gap-2 mb-3">
        <span className="text-ui-micro text-muted-foreground uppercase tracking-wider">
          {idea.domain}
        </span>
        {!idea.has_proposal && (
          <span className="text-ui-micro text-muted-foreground">idea only</span>
        )}
      </div>

      {/* ScoreReport compact — scannable in triage */}
      <div className="flex items-center gap-2">
        {idea.novelty_score != null && (
          <ScoreReport kind="novelty" summary={idea.novelty_score} compact />
        )}
        {idea.feasibility_score != null && (
          <ScoreReport kind="feasibility" summary={idea.feasibility_score} compact />
        )}
        <span className="text-ui-micro text-muted-foreground ml-auto flex items-center gap-0.5">
          Open <Chevron className="h-3 w-3" />
        </span>
      </div>
    </div>
  );
}
