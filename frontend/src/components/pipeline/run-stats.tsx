import React from "react";

interface RunStatsData {
  total_runs: number;
  by_status: Record<string, number>;
  avg_duration_s: number;
  total_ideas: number;
  total_gaps: number;
}

interface RunStatsProps {
  stats: RunStatsData | null;
  loading?: boolean;
}

/**
 * RunStats: Displays aggregate pipeline run statistics.
 * Shows total runs, status breakdown, avg duration, ideas, gaps.
 */
export function RunStats({ stats, loading }: RunStatsProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="animate-pulse bg-gray-200 dark:bg-gray-700 rounded-lg h-20" />
        ))}
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="text-center text-gray-500 py-8">
        No pipeline statistics available yet.
      </div>
    );
  }

  const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${seconds.toFixed(0)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  const cards = [
    { label: "Total Runs", value: stats.total_runs, color: "text-blue-600" },
    { label: "Avg Duration", value: formatDuration(stats.avg_duration_s), color: "text-purple-600" },
    { label: "Ideas Generated", value: stats.total_ideas, color: "text-green-600" },
    { label: "Gaps Found", value: stats.total_gaps, color: "text-orange-600" },
    { label: "Success Rate", value: formatSuccessRate(stats.by_status), color: "text-emerald-600" },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4"
        >
          <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            {card.label}
          </div>
          <div className={`text-2xl font-bold mt-1 ${card.color}`}>
            {card.value}
          </div>
        </div>
      ))}
    </div>
  );
}

function formatSuccessRate(byStatus: Record<string, number>): string {
  const total = Object.values(byStatus).reduce((a, b) => a + b, 0);
  if (total === 0) return "—";
  const completed = byStatus["completed"] || 0;
  return `${Math.round((completed / total) * 100)}%`;
}

export default RunStats;
