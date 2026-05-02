/**
 * CostSummaryCard — BATCH-18/TASK-02
 *
 * Displays total cost, token count, and event count in a summary card.
 */

import type { CostSummary } from "@/api/costs";

interface CostSummaryCardProps {
  summary: CostSummary;
}

function formatUSD(value: number): string {
  return `$${value.toFixed(4)}`;
}

function formatNumber(value: number): string {
  return value.toLocaleString();
}

export function CostSummaryCard({ summary }: CostSummaryCardProps) {
  return (
    <div className="rounded-lg border bg-card p-6 space-y-4" data-testid="cost-summary-card">
      <h3 className="text-sm font-medium text-muted-foreground">Total Spend</h3>
      <p className="text-3xl font-bold" data-testid="total-cost">
        {formatUSD(summary.total_cost_usd)}
      </p>
      <div className="flex gap-6 text-sm text-muted-foreground">
        <div>
          <span className="font-medium text-foreground" data-testid="total-tokens">
            {formatNumber(summary.total_tokens)}
          </span>{" "}
          tokens
        </div>
        <div>
          <span className="font-medium text-foreground" data-testid="event-count">
            {formatNumber(summary.event_count)}
          </span>{" "}
          events
        </div>
      </div>
    </div>
  );
}
