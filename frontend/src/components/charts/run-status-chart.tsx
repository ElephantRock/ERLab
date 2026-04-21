import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import type { PipelineRunSummary } from "@/api/types";

interface RunStatusChartProps {
  runs: PipelineRunSummary[];
}

const STATUS_COLORS: Record<string, string> = {
  completed: "#10b981",
  running: "#3b82f6",
  pending: "#f59e0b",
  failed: "#ef4444",
};

function buildData(runs: PipelineRunSummary[]) {
  const counts: Record<string, number> = {};
  for (const run of runs) {
    counts[run.status] = (counts[run.status] || 0) + 1;
  }
  return Object.entries(counts).map(([name, value]) => ({ name, value }));
}

export function RunStatusChart({ runs }: RunStatusChartProps) {
  const data = buildData(runs);

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
        >
          {data.map((entry) => (
            <Cell key={entry.name} fill={STATUS_COLORS[entry.name] || "#94a3b8"} />
          ))}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
