/**
 * CostsPage — BATCH-18/TASK-03
 *
 * Full Cost Dashboard page replacing the /costs placeholder.
 * Shows: total spend summary, cost breakdowns by provider/stage/model,
 * per-run cost list, and budget utilization bar.
 */

import { useEffect, useState } from "react";
import {
  getCostSummary,
  getCostByProvider,
  getCostByStage,
  getCostByModel,
  getRunCostBreakdown,
} from "@/api/costs";
import type {
  CostSummary,
  ProviderBreakdown,
  StageBreakdown,
  ModelBreakdown,
  RunCostBreakdown,
} from "@/api/costs";
import { CostSummaryCard } from "@/components/costs/cost-summary-card";
import { CostBreakdownTable } from "@/components/costs/cost-breakdown-table";
import { BudgetBar } from "@/components/costs/budget-bar";

/** Default budget limit in USD (matches backend budget_max_cost_usd default) */
const DEFAULT_BUDGET_LIMIT = 10.0;

export default function CostsPage() {
  const [summary, setSummary] = useState<CostSummary | null>(null);
  const [byProvider, setByProvider] = useState<ProviderBreakdown>({});
  const [byStage, setByStage] = useState<StageBreakdown>({});
  const [byModel, setByModel] = useState<ModelBreakdown>({});
  const [runCosts, setRunCosts] = useState<RunCostBreakdown[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [sum, prov, stage, model] = await Promise.all([
          getCostSummary(),
          getCostByProvider(),
          getCostByStage(),
          getCostByModel(),
        ]);
        if (cancelled) return;

        setSummary(sum);
        setByProvider(prov);
        setByStage(stage);
        setByModel(model);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load cost data");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, []);

  async function handleLoadRun(runId: string) {
    try {
      const data = await getRunCostBreakdown(runId);
      setRunCosts((prev) => [...prev, data]);
    } catch {
      // Silently ignore — run data is optional
    }
  }

  const currentSpend = summary?.total_cost_usd ?? 0;

  if (loading) {
    return (
      <div className="space-y-6" data-testid="costs-page">
        <h1 className="text-2xl font-bold tracking-tight">Cost Dashboard</h1>
        <p className="text-muted-foreground">Loading cost data…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6" data-testid="costs-page">
        <h1 className="text-2xl font-bold tracking-tight">Cost Dashboard</h1>
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-800" data-testid="cost-error">
          <p className="font-medium">Error loading cost data</p>
          <p className="text-sm">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="costs-page">
      <h1 className="text-2xl font-bold tracking-tight">Cost Dashboard</h1>

      {/* Summary + Budget */}
      <div className="grid gap-6 md:grid-cols-2">
        <div data-testid="cost-summary-section">
          {summary && <CostSummaryCard summary={summary} />}
        </div>
        <div data-testid="budget-section">
          <BudgetBar currentSpend={currentSpend} budgetLimit={DEFAULT_BUDGET_LIMIT} />
        </div>
      </div>

      {/* Breakdown tables */}
      <div className="grid gap-6 lg:grid-cols-2" data-testid="cost-breakdown-section">
        <CostBreakdownTable
          title="Cost by Provider"
          data={byProvider}
          labelColumn="Provider"
        />
        <CostBreakdownTable
          title="Cost by Stage"
          data={byStage}
          labelColumn="Stage"
        />
      </div>

      <CostBreakdownTable
        title="Cost by Model"
        data={byModel}
        labelColumn="Model"
      />

      {/* Per-run cost list */}
      <div data-testid="run-costs-section">
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-sm font-medium text-muted-foreground mb-4">
            Per-Run Cost Breakdown
          </h3>
          {runCosts.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No run cost data loaded. Use the run ID lookup below.
            </p>
          ) : (
            <div className="space-y-4">
              {runCosts.map((rc) => (
                <div key={rc.run_id} className="border rounded-lg p-4">
                  <p className="font-medium mb-2">Run: {rc.run_id}</p>
                  <p className="text-sm text-muted-foreground">
                    Total: ${rc.summary.total_cost_usd.toFixed(4)} —{" "}
                    {rc.summary.event_count} events
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
