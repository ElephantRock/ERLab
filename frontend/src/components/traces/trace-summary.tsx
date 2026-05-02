/**
 * TraceSummary — BATCH-21/TASK-01
 *
 * Displays total traces, active traces, and error rate in a summary card.
 */

import type { TraceSummary as TraceSummaryData } from "@/api/traces";

interface TraceSummaryProps {
  summary: TraceSummaryData;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function TraceSummary({ summary }: TraceSummaryProps) {
  return (
    <div className="rounded-lg border bg-card p-6 space-y-4" data-testid="trace-summary">
      <h3 className="text-sm font-medium text-muted-foreground">Trace Overview</h3>
      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <p className="text-3xl font-bold" data-testid="total-traces">
            {summary.total_traces.toLocaleString()}
          </p>
          <p className="text-sm text-muted-foreground">Total Traces</p>
        </div>
        <div>
          <p className="text-3xl font-bold" data-testid="active-traces">
            {summary.active_traces.toLocaleString()}
          </p>
          <p className="text-sm text-muted-foreground">Active Traces</p>
        </div>
        <div>
          <p className="text-3xl font-bold" data-testid="error-rate">
            {formatPercent(summary.error_rate)}
          </p>
          <p className="text-sm text-muted-foreground">Error Rate</p>
        </div>
      </div>
    </div>
  );
}
