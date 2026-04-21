import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { PipelineRunSummary } from "@/api/types";
import { cn } from "@/lib/utils";

interface RunCardProps {
  run: PipelineRunSummary;
  onClick?: () => void;
}

const statusColors: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

export function RunCard({ run, onClick }: RunCardProps) {
  return (
    <Card
      className={cn("cursor-pointer transition-colors hover:bg-accent/50", onClick && "cursor-pointer")}
      onClick={onClick}
    >
      <CardContent className="flex items-center justify-between p-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Run #{run.id}</span>
            <Badge className={cn("text-xs", statusColors[run.status])} variant="secondary">
              {run.status}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-1">{run.domain}</p>
        </div>
        <div className="text-right flex-shrink-0 ml-4">
          {run.ideas_count > 0 && (
            <span className="text-sm font-medium">{run.ideas_count} ideas</span>
          )}
          <p className="text-xs text-muted-foreground">
            {new Date(run.created_at).toLocaleDateString()}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
