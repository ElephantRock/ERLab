import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import type { IdeaSummary } from "@/api/types";

interface DomainBreakdownChartProps {
  ideas: IdeaSummary[];
}

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"];

function buildData(ideas: IdeaSummary[]) {
  const counts: Record<string, number> = {};
  for (const idea of ideas) {
    const domain = idea.domain || "Unspecified";
    counts[domain] = (counts[domain] || 0) + 1;
  }
  return Object.entries(counts)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);
}

export function DomainBreakdownChart({ ideas }: DomainBreakdownChartProps) {
  const data = buildData(ideas);

  if (data.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={100}
          paddingAngle={2}
          dataKey="value"
          label={({ name, percent }) => `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`}
          labelLine={false}
        >
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
