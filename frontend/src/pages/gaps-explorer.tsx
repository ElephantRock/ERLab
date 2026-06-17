import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { listGaps } from "@/api/gaps";
import { GapCard } from "@/components/gaps/gap-card";
import { ErrorCard } from "@/components/ui/error-card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { GitBranch, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { ClusterScatterPlot } from "@/components/gaps/cluster-scatter";
import { apiFetch } from "@/api/client";
import type { ResearchGap } from "@/api/types";

const SORT_OPTIONS = [
  { value: "confidence", label: "Confidence" },
  { value: "date", label: "Date" },
  { value: "type", label: "Type" },
] as const;

const GAP_TYPE_OPTIONS = [
  { value: "", label: "All Types" },
  { value: "methodological", label: "Methodological" },
  { value: "empirical", label: "Empirical" },
  { value: "theoretical", label: "Theoretical" },
  { value: "cross-domain", label: "Cross-domain" },
] as const;

export default function GapsExplorer() {
  const navigate = useNavigate();
  const [searchText, setSearchText] = useState("");
  const [gapTypeFilter, setGapTypeFilter] = useState("");
  const [sortBy, setSortBy] = useState("confidence");
  const [minConfidence, setMinConfidence] = useState(0);
  const [page, setPage] = useState(0);
  const [activeTab, setActiveTab] = useState<"gaps" | "clusters">("gaps");
  const [clusterFilter, setClusterFilter] = useState<number | null>(null);
  const limit = 20;

  const queryParams = useMemo(
    () => ({
      search: searchText || undefined,
      gap_type: gapTypeFilter || undefined,
      sort_by: sortBy,
      sort_order: "desc",
      min_confidence: minConfidence > 0 ? minConfidence : undefined,
      limit,
      offset: page * limit,
    }),
    [searchText, gapTypeFilter, sortBy, minConfidence, page, limit],
  );

  const { data, isLoading, isError } = useQuery({
    queryKey: ["gaps", queryParams],
    queryFn: () => listGaps(queryParams),
  });

  const { data: clusterData } = useQuery({
    queryKey: ["gap-clusters"],
    queryFn: () => apiFetch("/gaps/clusters") as Promise<{ clusters: any[]; total_papers: number }>,
    enabled: activeTab === "clusters",
  });

  const handleIdeaCountClick = (gap: ResearchGap) => {
    navigate(`/ideas?search=${encodeURIComponent(gap.title)}`);
  };

  const handleClusterClick = (clusterId: number) => {
    setClusterFilter(clusterFilter === clusterId ? null : clusterId);
    setActiveTab("gaps");
    setPage(0);
  };

  const resetFilters = () => {
    setSearchText("");
    setGapTypeFilter("");
    setSortBy("confidence");
    setMinConfidence(0);
    setPage(0);
  };

  const hasActiveFilters =
    searchText !== "" || gapTypeFilter !== "" || sortBy !== "confidence" || minConfidence > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Research Gaps</h1>
          <p className="text-muted-foreground">
            Identified gaps in the literature, sorted by confidence.
          </p>
        </div>
        <div className="flex gap-1">
          <Button
            variant={activeTab === "gaps" ? "default" : "outline"}
            size="sm"
            onClick={() => setActiveTab("gaps")}
          >
            Gaps
          </Button>
          <Button
            variant={activeTab === "clusters" ? "default" : "outline"}
            size="sm"
            onClick={() => setActiveTab("clusters")}
          >
            Clusters
          </Button>
        </div>
      </div>

      {activeTab === "gaps" ? (
      <>
      {clusterFilter !== null && (
        <div className="flex items-center gap-2">
          <Badge variant="secondary" data-testid="cluster-filter-badge">
            Cluster {clusterFilter}
          </Badge>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setClusterFilter(null)}
          >
            Clear
          </Button>
        </div>
      )}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search gaps by title or description..."
            value={searchText}
            onChange={(e) => {
              setSearchText(e.target.value);
              setPage(0);
            }}
            className="pl-9"
            aria-label="Search gaps by title or description"
          />
        </div>

        <div className="flex items-end gap-4">
          <div className="w-[180px]">
            <label className="text-xs text-muted-foreground mb-1 block">Gap Type</label>
            <Select
              value={gapTypeFilter}
              onValueChange={(v) => {
                setGapTypeFilter(v);
                setPage(0);
              }}
            >
              <SelectTrigger aria-label="Filter by gap type">
                <SelectValue placeholder="All Types" />
              </SelectTrigger>
              <SelectContent>
                {GAP_TYPE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value || "__all__"}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="w-[160px]">
            <label className="text-xs text-muted-foreground mb-1 block">
              Min Confidence: {minConfidence.toFixed(1)}
            </label>
            <Slider
              value={[minConfidence]}
              onValueChange={(v) => {
                setMinConfidence(v[0]);
                setPage(0);
              }}
              min={0}
              max={1}
              step={0.1}
              aria-label="Minimum confidence filter"
            />
          </div>

          <div className="w-[160px]">
            <label className="text-xs text-muted-foreground mb-1 block">Sort by</label>
            <Select
              value={sortBy}
              onValueChange={(v) => {
                setSortBy(v);
                setPage(0);
              }}
            >
              <SelectTrigger aria-label="Sort gaps by">
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

          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={resetFilters}
              className="whitespace-nowrap"
            >
              Reset
            </Button>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : isError ? (
        <ErrorCard message="Failed to load research gaps" testId="gaps-error" />
      ) : data?.gaps.length ? (
        <>
          <p className="text-sm text-muted-foreground">
            {data.total} gap{data.total !== 1 ? "s" : ""} found
          </p>
          <div className="space-y-3">
            {data.gaps.map((gap) => (
              <GapCard
                key={gap.id}
                gap={gap}
                onIdeaCountClick={handleIdeaCountClick}
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
        <EmptyState
          icon={GitBranch}
          title="No research gaps found"
          message={searchText ? `No gaps match "${searchText}".` : "No gaps have been identified yet."}
          testId="gaps-empty"
        />
      )}
      </>
      ) : (
        <div>
          {clusterData?.clusters?.length ? (
            <ClusterScatterPlot
              clusters={clusterData.clusters}
              onClusterClick={handleClusterClick}
              selectedClusterId={clusterFilter}
            />
          ) : (
            <p className="text-sm text-muted-foreground py-4">No cluster data available.</p>
          )}
          {clusterData && (
            <p className="text-sm text-muted-foreground mt-2">
              {clusterData.total_papers} papers across {clusterData.clusters.length} clusters
            </p>
          )}
        </div>
      )
      }
    </div>
  );
}
