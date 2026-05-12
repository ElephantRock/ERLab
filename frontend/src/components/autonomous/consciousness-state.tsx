import { Badge } from "@/components/ui/badge";
import type { ConsciousnessState } from "@/api/autonomous";

interface ConsciousnessStateBadgeProps {
  state: ConsciousnessState;
  secondsInState?: number;
}

const STATE_CONFIG: Record<ConsciousnessState, { label: string; color: string }> = {
  idle: { label: "Idle", color: "bg-muted/50 text-muted-foreground" },
  exploring: { label: "Exploring", color: "bg-info/10 text-info" },
  generating: { label: "Generating", color: "bg-info/10 text-info" },
  evaluating: { label: "Evaluating", color: "bg-warning/10 text-warning" },
  synthesizing: { label: "Synthesizing", color: "bg-success/10 text-success" },
  resting: { label: "Resting", color: "bg-indigo-100 text-indigo-800" },
};

export function ConsciousnessStateBadge({ state, secondsInState }: ConsciousnessStateBadgeProps) {
  const config = STATE_CONFIG[state] || STATE_CONFIG.idle;

  return (
    <div className="flex items-center gap-2" data-testid="consciousness-state">
      <Badge className={config.color} data-testid="consciousness-badge">
        {config.label}
      </Badge>
      {secondsInState !== undefined && (
        <span className="text-xs text-muted-foreground" data-testid="consciousness-seconds">
          {Math.round(secondsInState)}s
        </span>
      )}
    </div>
  );
}
