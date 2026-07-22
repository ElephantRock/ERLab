/**
 * Gaps Explorer — Triage Surface.
 *
 * PRODUCT.md §5: density allowed here (scanning). Same contract compliance
 * as ideas-browser: useResource + DataView, ui-scale typography.
 */

import { useState, useMemo } from "react";
import { useResource } from "@/lib/useResource";
import { DataView } from "@/components/ui/data-view";
import { listGaps } from "@/api/gaps";
import { GapCard } from "@/components/gaps/gap-card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { useQuery } from "@tanstack/react-query";
import { getGapClusters } from "@/api/gaps";

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

  // INTERFACE_CONTRACT §1: useResource for the main gaps list.
  const resource = useResource(["gaps", queryParams], () => listGaps(queryParams));

  // Clusters use useQuery with enabled flag (conditional fetch — the contract
  // allows this for freshness/conditional queries with a cited reason).
  const { data: clusterData, isError: clustersError, refetch: refetchClusters } = useQuery({
    queryKey: ["gap-clusters"],
    queryFn: () => getGapClusters(),
    enabled: activeTab === "clusters",
  });

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
    <div className="space-y-6 animate-fade-in">
      {/* ── Header ── */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <GitBranch className="h-5 w-5 text-accent" />
            <h1 className="text-ui-display font-display font-semibold tracking-tight">
              Gaps
            </h1>
          </div>
          <p className="text-ui-meta text-muted-foreground">
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
              <Button variant="ghost" size="sm" onClick={() => setClusterFilter(null)}>
                Clear
              </Button>
            </div>
          )}

          {/* ── Filters ── */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search gaps by title or description..."
                value={searchText}
                onChange={(e) => { setSearchText(e.target.value); setPage(0); }}
                className="pl-9"
                aria-label="Search gaps by title or description"
              />
            </div>
            <div className="flex items-end gap-4">
              <div className="w-[180px]">
                <label className="text-ui-meta text-muted-foreground mb-1 block">Gap Type</label>
                <Select value={gapTypeFilter || "__all__"} onValueChange={(v) => { setGapTypeFilter(v === "__all__" ? "" : v); setPage(0); }}>
                  <SelectTrigger aria-label="Filter by gap type"><SelectValue placeholder="All Types" /></SelectTrigger>
                  <SelectContent>
                    {GAP_TYPE_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value || "__all__"} value={opt.value || "__all__"}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="w-[160px]">
                <label className="text-ui-meta text-muted-foreground mb-1 block">
                  Min Confidence: {minConfidence.toFixed(1)}
                </label>
                <Slider
                  value={[minConfidence]}
                  onValueChange={(v) => { setMinConfidence(v[0] ?? 0); setPage(0); }}
                  min={0} max={1} step={0.1}
                  aria-label="Minimum confidence filter"
                />
              </div>
              <div className="w-[160px]">
                <label className="text-ui-meta text-muted-foreground mb-1 block">Sort by</label>
                <Select value={sortBy} onValueChange={(v) => { setSortBy(v); setPage(0); }}>
                  <SelectTrigger aria-label="Sort gaps by"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {SORT_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {hasActiveFilters && (
                <Button variant="ghost" size="sm" onClick={resetFilters} className="whitespace-nowrap">
                  Reset
                </Button>
              )}
            </div>
          </div>

          {/* ── Results via DataView ── */}
          <DataView
            resource={resource}
            testId="gaps"
            empty={{
              what: "gaps",
              icon: GitBranch,
              title: searchText ? `No gaps match "${searchText}"` : "No research gaps found",
              message: searchText ? "Try adjusting your search." : "No gaps have been identified yet.",
            }}
          >
            {(data) => (
              <>
                <p className="text-ui-meta text-muted-foreground">
                  {data.total} gap{data.total !== 1 ? "s" : ""} found
                </p>
                <div className="space-y-3">
                  {data.gaps.map((gap) => (
                    <GapCard
                      key={gap.id}
                      gap={gap}
                      onIdeaCountClick={(g) => navigate(`/ideas?search=${encodeURIComponent(g.title)}`)}
                    />
                  ))}
                </div>
                {data.total > limit && (
                  <div className="flex items-center justify-between pt-4">
                    <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                      <ChevronLeft className="mr-1 h-4 w-4" />
                      Previous
                    </Button>
                    <span className="text-ui-meta text-muted-foreground">
                      Page {page + 1} of {Math.ceil(data.total / limit)}
                    </span>
                    <Button variant="outline" size="sm" disabled={(page + 1) * limit >= data.total} onClick={() => setPage((p) => p + 1)}>
                      Next
                      <ChevronRight className="ml-1 h-4 w-4" />
                    </Button>
                  </div>
                )}
              </>
            )}
          </DataView>
        </>
      ) : (
        <div>
          {clustersError ? (
            <div
              className="text-ui-meta text-destructive py-4"
              data-testid="clusters-error"
            >
              Failed to load clusters.{" "}
              <button onClick={() => refetchClusters()} className="underline">
                Retry
              </button>
            </div>
          ) : clusterData?.clusters?.length ? (
            <ClusterScatterPlot
              clusters={clusterData.clusters as never[]}
              onClusterClick={handleClusterClick}
              selectedClusterId={clusterFilter}
            />
          ) : (
            <p className="text-ui-meta text-muted-foreground py-4">No cluster data available.</p>
          )}
          {clusterData && (
            <p className="text-ui-meta text-muted-foreground mt-2">
              {clusterData.total_papers} papers across {clusterData.clusters.length} clusters
            </p>
          )}
        </div>
      )}
    </div>
  );
}
