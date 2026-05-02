import { useQuery } from "@tanstack/react-query";
import { listGaps } from "@/api/gaps";
import { GapCard } from "@/components/gaps/gap-card";
import { Skeleton } from "@/components/ui/skeleton";
import { GitBranch } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { ResearchGap } from "@/api/types";

export default function GapsExplorer() {
  const navigate = useNavigate();

  const { data, isLoading } = useQuery({
    queryKey: ["gaps"],
    queryFn: () => listGaps({ limit: 50 }),
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
