import { cn } from "@/lib/utils";
import { Check, Loader2 } from "lucide-react";
import type { StageProgress } from "@/hooks/usePipelineProgress";

interface StageProgressProps {
  stages: StageProgress[];
  currentStage: string | null;
}

export function StageProgress({ stages }: StageProgressProps) {
  return (
    <div className="space-y-2">
      {stages.map((stage, i) => (
        <div key={stage.key} className="flex items-center gap-3">
          <div className="flex-shrink-0">
            {stage.status === "completed" ? (
              <div className="h-7 w-7 rounded-full bg-green-100 text-green-600 flex items-center justify-center">
                <Check className="h-4 w-4" />
              </div>
            ) : stage.status === "running" ? (
              <div className="h-7 w-7 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center">
                <Loader2 className="h-4 w-4 animate-spin" />
              </div>
            ) : (
              <div className="h-7 w-7 rounded-full bg-muted text-muted-foreground flex items-center justify-center">
                <span className="text-xs">{i + 1}</span>
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <p
              className={cn(
                "text-sm font-medium truncate",
                stage.status === "completed"
                  ? "text-green-700"
                  : stage.status === "running"
                    ? "text-blue-700"
                    : "text-muted-foreground",
              )}
            >
              {stage.label}
            </p>
          </div>
          {stage.status === "running" && (
            <span className="text-xs text-muted-foreground">{stage.elapsed.toFixed(0)}s</span>
          )}
          {stage.status === "completed" && stage.elapsed > 0 && (
            <span className="text-xs text-muted-foreground">{stage.elapsed.toFixed(0)}s</span>
          )}
        </div>
      ))}
    </div>
  );
}
