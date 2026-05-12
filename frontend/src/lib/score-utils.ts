export type NoveltyLabel = "Low" | "Moderate" | "High" | "Very High";
export type FeasibilityLabel = "Difficult" | "Moderate" | "Feasible" | "Very Feasible";

export function getNoveltyLabel(score: number): NoveltyLabel {
  if (score >= 0.8) return "Very High";
  if (score >= 0.6) return "High";
  if (score >= 0.3) return "Moderate";
  return "Low";
}

export function getFeasibilityLabel(score: number): FeasibilityLabel {
  if (score >= 8) return "Very Feasible";
  if (score >= 6) return "Feasible";
  if (score >= 3) return "Moderate";
  return "Difficult";
}

export function getScoreColor(score: number, scale: "novelty" | "feasibility"): string {
  const normalized = scale === "feasibility" ? score / 10 : score;
  if (normalized >= 0.8) return "text-success";
  if (normalized >= 0.6) return "text-success";
  if (normalized >= 0.3) return "text-warning";
  return "text-destructive";
}

export function getScoreBg(score: number, scale: "novelty" | "feasibility"): string {
  const normalized = scale === "feasibility" ? score / 10 : score;
  if (normalized >= 0.8) return "bg-success/10 text-success";
  if (normalized >= 0.6) return "bg-success/10 text-success";
  if (normalized >= 0.3) return "bg-warning/10 text-warning";
  return "bg-destructive/10 text-destructive";
}
