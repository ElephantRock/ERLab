import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { listGaps } from "@/api/gaps";
import { GapCard } from "@/components/gaps/gap-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { GitBranch, ChevronLeft, ChevronRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { ResearchGap } from "@/api/types";

export default function GapsExplorer() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const limit = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["gaps", { limit, offset: page * limit }],
    queryFn: () => listGaps({ limit, offset: page * limit }),
  });

  const handleIdeaCountClick = (gap: ResearchGap) => {
    navigate(`/ideas?search=${encodeURIComponent(gap.title)}`);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Research Gaps</h1>
        <p className="text-muted-foreground">
          Identified gaps in the literature, sorted by confidence.
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : data?.gaps.length ? (
        <>
          <p className="text-sm text-muted-foreground">
            {data.total} gap{data.total !== 1 ? "s" : ""} identified
          </p>
          <div className="space-y-3">
            {data.gaps
              .sort((a, b) => b.confidence - a.confidence)
              .map((gap) => (
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
        <div className="text-center py-12 text-muted-foreground">
          <GitBranch className="h-8 w-8 mx-auto mb-2 opacity-50" />
          <p>No research gaps found. Run a pipeline to discover gaps.</p>
        </div>
      )}
    </div>
  );
}
