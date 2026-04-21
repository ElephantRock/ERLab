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
  if (normalized >= 0.8) return "text-green-600";
  if (normalized >= 0.6) return "text-emerald-500";
  if (normalized >= 0.3) return "text-amber-500";
  return "text-red-500";
}

export function getScoreBg(score: number, scale: "novelty" | "feasibility"): string {
  const normalized = scale === "feasibility" ? score / 10 : score;
  if (normalized >= 0.8) return "bg-green-100 text-green-800";
  if (normalized >= 0.6) return "bg-emerald-100 text-emerald-800";
  if (normalized >= 0.3) return "bg-amber-100 text-amber-800";
  return "bg-red-100 text-red-800";
}
