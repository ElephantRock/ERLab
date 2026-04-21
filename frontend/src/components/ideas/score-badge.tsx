import { cn } from "@/lib/utils";
import { getScoreBg, getNoveltyLabel, getFeasibilityLabel } from "@/lib/score-utils";

interface ScoreBadgeProps {
  score: number;
  scale: "novelty" | "feasibility";
}

export function ScoreBadge({ score, scale }: ScoreBadgeProps) {
  const label = scale === "novelty" ? getNoveltyLabel(score) : getFeasibilityLabel(score);
  const display = scale === "feasibility" ? `${score}/10` : score.toFixed(2);

  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold", getScoreBg(score, scale))}>
      {display} {label}
    </span>
  );
}
