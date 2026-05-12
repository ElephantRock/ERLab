import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ResearchGap } from "@/api/types";
import { cn } from "@/lib/utils";
import { Lightbulb } from "lucide-react";
import { useNavigate } from "react-router-dom";

interface GapCardProps {
  gap: ResearchGap;
  onIdeaCountClick?: (gap: ResearchGap) => void;
}

function confidenceColor(confidence: number): string {
  if (confidence >= 0.8) return "bg-success";
  if (confidence >= 0.6) return "bg-success/70";
  if (confidence >= 0.3) return "bg-warning";
  return "bg-destructive";
}

export function GapCard({ gap, onIdeaCountClick }: GapCardProps) {
  const navigate = useNavigate();
  const ideaCount = gap.idea_count ?? 0;

  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow"
      onClick={() => navigate(`/gaps/${gap.id}`)}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-medium leading-tight">{gap.title}</h3>
            <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{gap.description}</p>
            <div className="flex items-center gap-2 mt-2">
              <Badge variant="outline" className="text-xs">
                {gap.gap_type}
              </Badge>
              {gap.potential_impact && (
                <span className="text-xs text-muted-foreground">{gap.potential_impact}</span>
              )}
              {ideaCount > 0 && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onIdeaCountClick?.(gap);
                  }}
                  className="inline-flex items-center gap-1 rounded-full bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning hover:bg-warning/15 transition-colors cursor-pointer"
                  aria-label={`${ideaCount} idea${ideaCount !== 1 ? "s" : ""} generated`}
                >
                  <Lightbulb className="h-3 w-3" />
                  {ideaCount} idea{ideaCount !== 1 ? "s" : ""}
                </button>
              )}
            </div>
          </div>
          <div className="flex-shrink-0 flex flex-col items-center gap-1">
            <span className="text-xs text-muted-foreground">
              {(gap.confidence * 100).toFixed(0)}%
            </span>
            <div className="h-2 w-16 rounded-full bg-secondary overflow-hidden">
              <div
                className={cn("h-full rounded-full", confidenceColor(gap.confidence))}
                style={{ width: `${gap.confidence * 100}%` }}
              />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
