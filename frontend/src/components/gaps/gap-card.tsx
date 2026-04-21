import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ResearchGap } from "@/api/types";
import { cn } from "@/lib/utils";

interface GapCardProps {
  gap: ResearchGap;
}

function confidenceColor(confidence: number): string {
  if (confidence >= 0.8) return "bg-green-500";
  if (confidence >= 0.6) return "bg-emerald-500";
  if (confidence >= 0.3) return "bg-amber-500";
  return "bg-red-500";
}

export function GapCard({ gap }: GapCardProps) {
  return (
    <Card>
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
