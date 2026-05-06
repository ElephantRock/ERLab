import { useMemo } from "react";

export interface DimensionScore {
  score: number;
  justification: string;
}

export interface ProposalEvaluationData {
  novelty: DimensionScore;
  feasibility: DimensionScore;
  completeness: DimensionScore;
  rigor: DimensionScore;
  clarity: DimensionScore;
  overall: number;
}

interface EvaluationCardProps {
  evaluation: ProposalEvaluationData | null;
}

const dimensionLabels: Record<string, string> = {
  novelty: "Novelty",
  feasibility: "Feasibility",
  completeness: "Completeness",
  rigor: "Rigor",
  clarity: "Clarity",
};

function scoreColor(score: number): string {
  if (score >= 0.8) return "bg-green-500";
  if (score >= 0.6) return "bg-yellow-500";
  if (score >= 0.4) return "bg-orange-500";
  return "bg-red-500";
}

function scoreTextColor(score: number): string {
  if (score >= 0.8) return "text-green-700";
  if (score >= 0.6) return "text-yellow-700";
  if (score >= 0.4) return "text-orange-700";
  return "text-red-700";
}

export function EvaluationCard({ evaluation }: EvaluationCardProps) {
  const dimensions = useMemo(() => {
    if (!evaluation) return [];
    return Object.entries(dimensionLabels).map(([key, label]) => ({
      key,
      label,
      score: (evaluation as any)[key]?.score ?? 0,
      justification: (evaluation as any)[key]?.justification ?? "",
    }));
  }, [evaluation]);

  if (!evaluation) {
    return (
      <div className="text-sm text-muted-foreground p-4 border rounded-md">
        No evaluation available for this proposal.
      </div>
    );
  }

  return (
    <div className="border rounded-md p-4 space-y-3" data-testid="evaluation-card">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Proposal Evaluation</h3>
        <span className={`text-lg font-bold ${scoreTextColor(evaluation.overall)}`}>
          {evaluation.overall.toFixed(2)}
        </span>
      </div>

      {/* Dimension bars */}
      <div className="space-y-2">
        {dimensions.map((dim) => (
          <div key={dim.key} className="space-y-0.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium">{dim.label}</span>
              <span className={scoreTextColor(dim.score)}>{dim.score.toFixed(2)}</span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${scoreColor(dim.score)} transition-all`}
                style={{ width: `${Math.round(dim.score * 100)}%` }}
              />
            </div>
            {dim.justification && (
              <p className="text-xs text-muted-foreground">{dim.justification}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
