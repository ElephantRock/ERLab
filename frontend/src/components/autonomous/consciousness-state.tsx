import { Badge } from "@/components/ui/badge";
import type { ConsciousnessState } from "@/api/autonomous";

interface ConsciousnessStateBadgeProps {
  state: ConsciousnessState;
  secondsInState?: number;
}

const STATE_CONFIG: Record<ConsciousnessState, { label: string; color: string }> = {
  idle: { label: "Idle", color: "bg-gray-100 text-gray-800" },
  exploring: { label: "Exploring", color: "bg-blue-100 text-blue-800" },
  generating: { label: "Generating", color: "bg-purple-100 text-purple-800" },
  evaluating: { label: "Evaluating", color: "bg-orange-100 text-orange-800" },
  synthesizing: { label: "Synthesizing", color: "bg-green-100 text-green-800" },
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
