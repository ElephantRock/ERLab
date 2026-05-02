/**
 * BudgetBar — BATCH-18/TASK-02
 *
 * Visualizes budget utilization as a progress bar.
 * Shows current spend vs. configured budget limit.
 */

interface BudgetBarProps {
  currentSpend: number;
  budgetLimit: number;
}

function formatUSD(value: number): string {
  return `$${value.toFixed(2)}`;
}

export function BudgetBar({ currentSpend, budgetLimit }: BudgetBarProps) {
  const pct = budgetLimit > 0 ? Math.min((currentSpend / budgetLimit) * 100, 100) : 0;
  const isOverBudget = currentSpend > budgetLimit && budgetLimit > 0;

  const barColor = isOverBudget
    ? "bg-red-500"
    : pct > 80
      ? "bg-yellow-500"
      : "bg-green-500";

  return (
    <div className="rounded-lg border bg-card p-6" data-testid="budget-bar">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-muted-foreground">Budget Utilization</h3>
        <span className="text-sm font-medium" data-testid="budget-percentage">
          {pct.toFixed(1)}%
        </span>
      </div>
      <div className="h-3 w-full rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${barColor}`}
          style={{ width: `${pct}%` }}
          data-testid="budget-bar-fill"
        />
      </div>
      <div className="flex justify-between mt-2 text-xs text-muted-foreground">
        <span data-testid="budget-current">{formatUSD(currentSpend)} spent</span>
        <span data-testid="budget-limit">{formatUSD(budgetLimit)} limit</span>
      </div>
    </div>
  );
}
