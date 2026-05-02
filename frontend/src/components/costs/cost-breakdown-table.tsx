/**
 * CostBreakdownTable — BATCH-18/TASK-02
 *
 * Renders a table from a dict breakdown (by-provider, by-stage, by-model).
 * Uses Object.entries() to convert the dict into table rows.
 */

import type { BreakdownEntry } from "@/api/costs";

interface CostBreakdownTableProps {
  title: string;
  data: Record<string, BreakdownEntry>;
  labelColumn?: string;
}

function formatUSD(value: number): string {
  return `$${value.toFixed(4)}`;
}

function formatNumber(value: number): string {
  return value.toLocaleString();
}

export function CostBreakdownTable({
  title,
  data,
  labelColumn = "Name",
}: CostBreakdownTableProps) {
  const entries = Object.entries(data);

  if (entries.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-6" data-testid="cost-breakdown-table">
        <h3 className="text-sm font-medium text-muted-foreground mb-2">{title}</h3>
        <p className="text-sm text-muted-foreground">No data available.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-6" data-testid="cost-breakdown-table">
      <h3 className="text-sm font-medium text-muted-foreground mb-4">{title}</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="pb-2 pr-4 font-medium">{labelColumn}</th>
              <th className="pb-2 pr-4 font-medium text-right">Cost (USD)</th>
              <th className="pb-2 pr-4 font-medium text-right">Input Tokens</th>
              <th className="pb-2 pr-4 font-medium text-right">Output Tokens</th>
              <th className="pb-2 font-medium text-right">Calls</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([name, entry]) => (
              <tr key={name} className="border-b last:border-0">
                <td className="py-2 pr-4 font-medium">{name}</td>
                <td className="py-2 pr-4 text-right">{formatUSD(entry.cost_usd)}</td>
                <td className="py-2 pr-4 text-right">{formatNumber(entry.input_tokens)}</td>
                <td className="py-2 pr-4 text-right">{formatNumber(entry.output_tokens)}</td>
                <td className="py-2 text-right">{formatNumber(entry.calls)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
