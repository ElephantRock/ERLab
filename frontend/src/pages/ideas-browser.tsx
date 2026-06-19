import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { listIdeas } from "@/api/ideas";
import { IdeaCard } from "@/components/ideas/idea-card";
import { ExportDialog } from "@/components/export/export-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
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
  Search, ChevronLeft, ChevronRight, CheckSquare, Square,
  AlertTriangle, RotateCw, Play, Inbox, SlidersHorizontal,
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
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
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

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["ideas", queryParams],
    queryFn: () => listIdeas(queryParams),
  });

  const ideas = data?.ideas ?? [];
  const hasQualityIssues = ideas.some(
    (i) => i.quality_summary?.has_issues,
  );
  const hasGovernance = ideas.some((i) => i.governance_status);

  return (
    <div className="space-y-5 animate-fade-in" data-testid="ideas-browser">
      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Inbox className="h-5 w-5 text-accent" />
            <h1 className="text-2xl font-display font-semibold tracking-tight">
              Results
            </h1>
          </div>
          <p className="text-sm text-muted-foreground">
            {data?.total ?? "—"} research ideas generated from your pipeline runs.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {selectedIds.size > 0 && (
            <>
              <ExportDialog ideaIds={Array.from(selectedIds)} />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedIds(new Set())}
              >
                Clear ({selectedIds.size})
              </Button>
            </>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate("/pipeline/new")}
          >
            <Play className="mr-2 h-3.5 w-3.5" />
            New Run
          </Button>
        </div>
      </div>

      {/* ── Search bar ── */}
      {!isError && (
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search ideas by title..."
              value={searchText}
              onChange={(e) => {
                setSearchText(e.target.value);
                setPage(0);
              }}
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
      )}

      {/* ── Expandable filter panel ── */}
      {!isError && showFilters && (
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end rounded-lg border border-border bg-card p-4 animate-fade-in">
          <div className="w-full sm:w-[180px]">
            <label className="text-xs text-muted-foreground mb-1 block">Sort by</label>
            <Select
              value={sortBy}
              onValueChange={(v) => {
                setSortBy(v);
                setPage(0);
              }}
            >
              <SelectTrigger aria-label="Sort ideas by">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SORT_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex-1">
            <label className="text-xs text-muted-foreground mb-1 block">
              Min Score: {minScore.toFixed(1)}
            </label>
            <Slider
              value={[minScore]}
              onValueChange={(v) => {
                setMinScore(v[0]);
                setPage(0);
              }}
              min={0}
              max={1}
              step={0.1}
              aria-label="Minimum overall score filter"
            />
          </div>

          <div className="w-full sm:w-[180px]">
            <label className="text-xs text-muted-foreground mb-1 block">Domain</label>
            <Input
              placeholder="Filter by domain..."
              value={domainFilter}
              onChange={(e) => {
                setDomainFilter(e.target.value);
                setPage(0);
              }}
              aria-label="Filter by domain"
            />
          </div>
        </div>
      )}

      {/* ── Loading ── */}
      {isLoading ? (
        <div className="grid gap-3 md:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      ) : isError ? (
        <div
          className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center space-y-4"
          data-testid="ideas-error"
          role="alert"
        >
          <AlertTriangle className="h-8 w-8 mx-auto text-destructive" />
          <div>
            <p className="font-medium text-destructive">Couldn't load ideas</p>
            <p className="text-sm text-muted-foreground mt-1">
              The backend may be offline or unreachable. Check your connection and try again.
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            <Button onClick={() => refetch()} data-testid="ideas-retry">
              <RotateCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate("/pipeline/new")}
              data-testid="ideas-start-pipeline"
            >
              <Play className="mr-2 h-4 w-4" />
              Start New Run
            </Button>
          </div>
        </div>
      ) : ideas.length ? (
        <>
          {/* ── Results grid ── */}
          <div className="grid gap-3 md:grid-cols-2">
            {ideas.map((idea) => (
              <div key={idea.id} className="relative">
                <div
                  className="absolute top-3 right-3 z-10"
                  onClick={(e) => e.stopPropagation()}
                  data-testid={`select-idea-${idea.id}`}
                >
                  <button
                    className="text-muted-foreground hover:text-primary transition-colors"
                    onClick={() => {
                      setSelectedIds((prev) => {
                        const next = new Set(prev);
                        if (next.has(idea.id)) {
                          next.delete(idea.id);
                        } else {
                          next.add(idea.id);
                        }
                        return next;
                      });
                    }}
                    aria-label={`Select idea ${idea.id}`}
                  >
                    {selectedIds.has(idea.id) ? (
                      <CheckSquare className="h-4 w-4 text-primary" />
                    ) : (
                      <Square className="h-4 w-4" />
                    )}
                  </button>
                </div>
                <IdeaCard
                  idea={idea}
                  onClick={() => navigate(`/ideas/${idea.id}`)}
                />
              </div>
            ))}
          </div>

          {/* ── Pagination ── */}
          {data && data.total > limit && (
            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft className="mr-1 h-4 w-4" />
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page + 1} of {Math.ceil(data.total / limit)}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={(page + 1) * limit >= data.total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
                <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            </div>
          )}
        </>
      ) : (
        <EmptyState
          icon={Search}
          title="No research ideas yet"
          message={searchText || domainFilter ? "No ideas match your filters." : "Run the pipeline to generate ideas from literature."}
          testId="ideas-empty"
          action={
            !searchText && !domainFilter ? (
              <Button onClick={() => navigate("/pipeline/new")}>
                <Play className="mr-2 h-4 w-4" />
                Start New Research Run
              </Button>
            ) : (
              <Button
                variant="outline"
                onClick={() => {
                  setSearchText("");
                  setDomainFilter("");
                  setMinScore(0);
                }}
              >
                Clear Filters
              </Button>
            )
          }
        />
      )}
    </div>
  );
}
