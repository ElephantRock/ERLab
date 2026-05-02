import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { listIdeas } from "@/api/ideas";
import { IdeaCard } from "@/components/ideas/idea-card";
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
import { Search, ChevronLeft, ChevronRight } from "lucide-react";

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

  const { data, isLoading } = useQuery({
    queryKey: ["ideas", queryParams],
    queryFn: () => listIdeas(queryParams),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Research Ideas</h1>
        <p className="text-muted-foreground">
          Browse generated ideas with novelty and feasibility scores.
        </p>
      </div>

      {/* Search, Sort, and Filter Controls */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
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

        <div className="flex items-end gap-4">
          <div className="w-[180px]">
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

          <div className="w-[160px]">
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

          <div className="w-[160px]">
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
      </div>

      {isLoading ? (
        <div className="grid gap-3 md:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      ) : data?.ideas.length ? (
        <>
          <p className="text-sm text-muted-foreground">
            {data.total} idea{data.total !== 1 ? "s" : ""} found
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            {data.ideas.map((idea) => (
              <IdeaCard
                key={idea.id}
                idea={idea}
                onClick={() => navigate(`/ideas/${idea.id}`)}
              />
            ))}
          </div>
          {data.total > limit && (
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
        <div className="text-center py-12 text-muted-foreground">
          <p>No ideas found{searchText ? ` for "${searchText}"` : domainFilter ? ` for "${domainFilter}"` : ""}.</p>
        </div>
      )}
    </div>
  );
}
