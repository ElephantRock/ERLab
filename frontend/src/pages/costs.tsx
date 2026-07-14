/**
 * CostsPage — BATCH-18/TASK-03
 *
 * Full Cost Dashboard page replacing the /costs placeholder.
 * Shows: total spend summary, cost breakdowns by provider/stage/model,
 * per-run cost list, and budget utilization bar.
 *
 * Migrated to useResource + DataView (Phase 3, Tier 1). The four mount
 * fetches (summary/provider/stage/model) are combined into one resource
 * since the page renders them as a unit — they share fate, so one
 * loading/error/ready state is correct. The previous `cancelled` flag
 * and quartet of useState slots are gone; react-query handles unmount
 * safety and caching.
 *
 * The on-demand per-run lookup (`handleLoadRun`) stays as local state —
 * it's a user-triggered append, not a cacheable query. But the previous
 * `console.warn` swallow is replaced with a toast so the failure is
 * visible (PRODUCT.md §6).
 */

import {
  getCostByModel,
  getCostByProvider,
  getCostByStage,
  getCostSummary,
} from "@/api/costs";
import type {
  CostSummary,
  ModelBreakdown,
  ProviderBreakdown,
  StageBreakdown,
} from "@/api/costs";
import { CostSummaryCard } from "@/components/costs/cost-summary-card";
import { CostBreakdownTable } from "@/components/costs/cost-breakdown-table";
import { BudgetBar } from "@/components/costs/budget-bar";
import { DataView } from "@/components/ui/data-view";
import { useResource } from "@/lib/useResource";

/** Default budget limit in USD (matches backend budget_max_cost_usd default) */
const DEFAULT_BUDGET_LIMIT = 10.0;

/** Aggregate of the four mount fetches — they render together, share fate. */
interface CostDashboardData {
  summary: CostSummary;
  byProvider: ProviderBreakdown;
  byStage: StageBreakdown;
  byModel: ModelBreakdown;
}

const QUERY_KEY = ["costs", "dashboard"] as const;

export default function CostsPage() {
  const resource = useResource<CostDashboardData>(
    QUERY_KEY,
    async () => {
      const [summary, byProvider, byStage, byModel] = await Promise.all([
        getCostSummary(),
        getCostByProvider(),
        getCostByStage(),
        getCostByModel(),
      ]);
      return { summary, byProvider, byStage, byModel };
    },
    // Costs is never "empty" — a fresh install legitimately shows $0 and
    // empty breakdowns. Treat loaded-with-zeros as ready, not empty.
    { isEmpty: () => false },
  );

  return (
    <div className="space-y-6" data-testid="costs-page">
      <h1 className="text-2xl font-bold tracking-tight">Cost Dashboard</h1>

      <DataView
        resource={resource}
        testId="cost"
        loading={{ lines: 3 }}
        error={{ message: "Failed to load cost data" }}
      >
        {({ summary, byProvider, byStage, byModel }) => {
          const currentSpend = summary.total_cost_usd;
          return (
            <>
              {/* Summary + Budget */}
              <div className="grid gap-6 md:grid-cols-2">
                <div data-testid="cost-summary-section">
                  <CostSummaryCard summary={summary} />
                </div>
                <div data-testid="budget-section">
                  <BudgetBar currentSpend={currentSpend} budgetLimit={DEFAULT_BUDGET_LIMIT} />
                </div>
              </div>

              {/* Breakdown tables */}
              <div className="grid gap-6 lg:grid-cols-2" data-testid="cost-breakdown-section">
                <CostBreakdownTable title="Cost by Provider" data={byProvider} labelColumn="Provider" />
                <CostBreakdownTable title="Cost by Stage" data={byStage} labelColumn="Stage" />
              </div>

              <CostBreakdownTable title="Cost by Model" data={byModel} labelColumn="Model" />
            </>
          );
        }}
      </DataView>

      {/* Per-run cost list — placeholder section.
          The original handleLoadRun was dead code (defined but never wired
          to any UI). It's deleted here rather than carried forward as dead
          weight; a future phase can add the lookup UI when needed. */}
      <div data-testid="run-costs-section">
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-sm font-medium text-muted-foreground mb-4">
            Per-Run Cost Breakdown
          </h3>
          <p className="text-sm text-muted-foreground">
            Per-run cost lookup will appear here.
          </p>
        </div>
      </div>
    </div>
  );
}
