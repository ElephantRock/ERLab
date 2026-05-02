import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CostSummaryCard } from "@/components/costs/cost-summary-card";
import { CostBreakdownTable } from "@/components/costs/cost-breakdown-table";
import { BudgetBar } from "@/components/costs/budget-bar";
import type { CostSummary, BreakdownEntry } from "@/api/costs";

const sampleSummary: CostSummary = {
  total_cost_usd: 1.2345,
  total_tokens: 150000,
  event_count: 42,
};

const sampleBreakdown: Record<string, BreakdownEntry> = {
  openai: { cost_usd: 0.5, input_tokens: 1000, output_tokens: 500, calls: 10 },
  anthropic: { cost_usd: 0.3, input_tokens: 800, output_tokens: 200, calls: 5 },
};

describe("BATCH-18/TASK-02: Cost Components", () => {
  // ── TEST-18-02-01: CostSummaryCard renders total cost and token counts
  it("TEST-18-02-01: CostSummaryCard renders total cost and token counts", () => {
    render(<CostSummaryCard summary={sampleSummary} />);

    expect(screen.getByTestId("cost-summary-card")).toBeInTheDocument();
    expect(screen.getByTestId("total-cost")).toHaveTextContent("$1.2345");
    expect(screen.getByTestId("total-tokens")).toHaveTextContent("150,000");
    expect(screen.getByTestId("event-count")).toHaveTextContent("42");
  });

  // ── TEST-18-02-02: CostBreakdownTable renders rows from data
  it("TEST-18-02-02: CostBreakdownTable renders rows from data", () => {
    render(
      <CostBreakdownTable
        title="Cost by Provider"
        data={sampleBreakdown}
        labelColumn="Provider"
      />,
    );

    expect(screen.getByTestId("cost-breakdown-table")).toBeInTheDocument();
    expect(screen.getByText("Cost by Provider")).toBeInTheDocument();

    // Verify table rows from Object.entries()
    expect(screen.getByText("openai")).toBeInTheDocument();
    expect(screen.getByText("anthropic")).toBeInTheDocument();

    // Verify cost values rendered
    expect(screen.getByText("$0.5000")).toBeInTheDocument();
    expect(screen.getByText("$0.3000")).toBeInTheDocument();
  });

  // ── TEST-18-02-03: BudgetBar renders utilization percentage
  it("TEST-18-02-03: BudgetBar renders utilization percentage", () => {
    render(<BudgetBar currentSpend={5} budgetLimit={10} />);

    expect(screen.getByTestId("budget-bar")).toBeInTheDocument();
    expect(screen.getByTestId("budget-percentage")).toHaveTextContent("50.0%");
    expect(screen.getByTestId("budget-current")).toHaveTextContent("$5.00 spent");
    expect(screen.getByTestId("budget-limit")).toHaveTextContent("$10.00 limit");
  });
});
