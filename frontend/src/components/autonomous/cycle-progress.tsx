import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { AutonomousCycleHistoryEntry } from "@/api/autonomous";

interface CycleProgressProps {
  cycle: AutonomousCycleHistoryEntry;
  /** Optional stop handler — triggers confirmation per HB-01. */
  onStop?: (cycleId: string) => void;
}

const STATUS_COLORS: Record<string, string> = {
  running: "bg-info/10 text-info",
  completed: "bg-success/10 text-success",
  stopped: "bg-warning/10 text-warning",
};

export function CycleProgress({ cycle, onStop }: CycleProgressProps) {
  return (
    <Card data-testid={`cycle-progress-${cycle.cycle_id}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-mono">{cycle.cycle_id}</CardTitle>
          <Badge className={STATUS_COLORS[cycle.status] || "bg-muted/50 text-muted-foreground"}>
            {cycle.status}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground" data-testid={`cycle-domain-${cycle.cycle_id}`}>
            {cycle.domain}
          </span>
          <span data-testid={`cycle-runs-${cycle.cycle_id}`}>
            {cycle.runs} run{cycle.runs !== 1 ? "s" : ""}
          </span>
        </div>
        {cycle.status === "running" && onStop && (
          <button
            className="mt-2 text-xs text-destructive hover:underline"
            data-testid={`cycle-stop-${cycle.cycle_id}`}
            onClick={() => onStop(cycle.cycle_id)}
          >
            Stop Cycle
          </button>
        )}
      </CardContent>
    </Card>
  );
}
