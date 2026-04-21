import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { getNoveltyLabel, getFeasibilityLabel } from "@/lib/score-utils";
import type { IdeaSummary } from "@/api/types";

interface ScoreDistributionChartProps {
  ideas: IdeaSummary[];
}

const bins = ["Low", "Moderate", "High", "Very High"];

function buildData(ideas: IdeaSummary[]) {
  const noveltyCounts: Record<string, number> = { Low: 0, Moderate: 0, High: 0, "Very High": 0 };
  const feasCounts: Record<string, number> = {
    Difficult: 0,
    Moderate: 0,
    Feasible: 0,
    "Very Feasible": 0,
  };

  for (const idea of ideas) {
    if (idea.novelty_score != null) {
      const label = getNoveltyLabel(idea.novelty_score);
      noveltyCounts[label] = (noveltyCounts[label] ?? 0) + 1;
    }
    if (idea.feasibility_score != null) {
      const label = getFeasibilityLabel(idea.feasibility_score);
      feasCounts[label] = (feasCounts[label] ?? 0) + 1;
    }
  }

  // Map feasibility labels to same bin names for grouped display
  const feasMapping: Record<string, string> = {
    Difficult: "Low",
    Moderate: "Moderate",
    Feasible: "High",
    "Very Feasible": "Very High",
  };

  return bins.map((bin) => ({
    bin,
    Novelty: noveltyCounts[bin] ?? 0,
    Feasibility:
      Object.entries(feasMapping)
        .filter(([, v]) => v === bin)
        .reduce((sum, [k]) => sum + (feasCounts[k] ?? 0), 0),
  }));
}

export function ScoreDistributionChart({ ideas }: ScoreDistributionChartProps) {
  const data = buildData(ideas);

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
        <XAxis dataKey="bin" tick={{ fontSize: 12 }} />
        <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
        <Tooltip />
        <Legend />
        <Bar dataKey="Novelty" fill="#3b82f6" radius={[4, 4, 0, 0]} />
        <Bar dataKey="Feasibility" fill="#10b981" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
