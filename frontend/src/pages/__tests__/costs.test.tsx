import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import CostsPage from "@/pages/costs";

// ── Mock the cost API ────────────────────────────────────────────

const mockSummary = {
  total_cost_usd: 2.5,
  total_tokens: 250000,
  event_count: 80,
};

const mockProvider = {
  openai: { cost_usd: 1.5, input_tokens: 2000, output_tokens: 500, calls: 20 },
  anthropic: { cost_usd: 1.0, input_tokens: 1000, output_tokens: 300, calls: 10 },
};

const mockStage = {
  generation: { cost_usd: 1.0, input_tokens: 1000, output_tokens: 400, calls: 15 },
  novelty_checking: { cost_usd: 0.8, input_tokens: 800, output_tokens: 200, calls: 10 },
};

const mockModel = {
  "openai/gpt-4": { cost_usd: 1.5, input_tokens: 2000, output_tokens: 500, calls: 20 },
  "anthropic/claude-3": { cost_usd: 1.0, input_tokens: 1000, output_tokens: 300, calls: 10 },
};

vi.mock("@/api/costs", () => ({
  getCostSummary: vi.fn(),
  getCostByProvider: vi.fn(),
  getCostByStage: vi.fn(),
  getCostByModel: vi.fn(),
  getRunCostBreakdown: vi.fn(),
}));

import {
  getCostSummary,
  getCostByProvider,
  getCostByStage,
  getCostByModel,
} from "@/api/costs";

function setupMocks() {
  vi.mocked(getCostSummary).mockResolvedValue(mockSummary);
  vi.mocked(getCostByProvider).mockResolvedValue(mockProvider);
  vi.mocked(getCostByStage).mockResolvedValue(mockStage);
  vi.mocked(getCostByModel).mockResolvedValue(mockModel);
}

// ── Helper ───────────────────────────────────────────────────────
// Uses the shared renderWithProviders (QueryClientProvider + router +
// settings/auth contexts) — the same wrapper the app shell provides.
// Previously this file hand-rolled a thinner MemoryRouter-only wrapper,
// which broke when the page migrated to useResource (react-query backed).

function renderCostsPage() {
  return renderWithProviders(<CostsPage />, { initialEntries: ["/costs"] });
}

describe("BATCH-18/TASK-03: Cost Dashboard Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── TEST-18-03-01: Cost dashboard renders without crashing ─────
  it("TEST-18-03-01: Cost dashboard renders without crashing", async () => {
    setupMocks();
    renderCostsPage();

    await waitFor(() => {
      expect(screen.getByTestId("costs-page")).toBeInTheDocument();
    });

    expect(screen.getByText("Cost Dashboard")).toBeInTheDocument();
  });

  // ── TEST-18-03-02: Shows cost summary section ──────────────────
  it("TEST-18-03-02: Shows cost summary section", async () => {
    setupMocks();
    renderCostsPage();

    await waitFor(() => {
      expect(screen.getByTestId("cost-summary-section")).toBeInTheDocument();
    });

    expect(screen.getByText("$2.5000")).toBeInTheDocument();
    expect(screen.getByText("80")).toBeInTheDocument();
  });

  // ── TEST-18-03-03: Shows breakdown tables (provider/stage/model) ─
  it("TEST-18-03-03: Shows breakdown tables (provider/stage/model)", async () => {
    setupMocks();
    renderCostsPage();

    await waitFor(() => {
      expect(screen.getByText("openai")).toBeInTheDocument();
    });

    // Provider table
    expect(screen.getByText("Cost by Provider")).toBeInTheDocument();
    expect(screen.getByText("anthropic")).toBeInTheDocument();

    // Stage table
    expect(screen.getByText("Cost by Stage")).toBeInTheDocument();
    expect(screen.getByText("generation")).toBeInTheDocument();
    expect(screen.getByText("novelty_checking")).toBeInTheDocument();

    // Model table
    expect(screen.getByText("Cost by Model")).toBeInTheDocument();
    expect(screen.getByText("openai/gpt-4")).toBeInTheDocument();
    expect(screen.getByText("anthropic/claude-3")).toBeInTheDocument();
  });

  // ── TEST-18-03-04: Shows per-run cost list ──────────────────────
  it("TEST-18-03-04: Shows per-run cost list", async () => {
    setupMocks();
    renderCostsPage();

    await waitFor(() => {
      expect(screen.getByTestId("run-costs-section")).toBeInTheDocument();
    });

    expect(screen.getByText("Per-Run Cost Breakdown")).toBeInTheDocument();
  });

  // ── TEST-18-03-05: Shows budget utilization bar ─────────────────
  it("TEST-18-03-05: Shows budget utilization bar", async () => {
    setupMocks();
    renderCostsPage();

    await waitFor(() => {
      expect(screen.getByTestId("budget-section")).toBeInTheDocument();
    });

    expect(screen.getByTestId("budget-bar")).toBeInTheDocument();
    // 2.5 / 10.0 = 25.0%
    expect(screen.getByTestId("budget-percentage")).toHaveTextContent("25.0%");
  });

  // ── TEST-18-03-06: Handles API error gracefully ────────────────
  it("TEST-18-03-06: Handles API error gracefully", async () => {
    vi.mocked(getCostSummary).mockRejectedValue(new Error("Network failure"));
    vi.mocked(getCostByProvider).mockRejectedValue(new Error("Network failure"));
    vi.mocked(getCostByStage).mockRejectedValue(new Error("Network failure"));
    vi.mocked(getCostByModel).mockRejectedValue(new Error("Network failure"));

    renderCostsPage();

    await waitFor(() => {
      expect(screen.getByTestId("cost-error")).toBeInTheDocument();
    });

    expect(screen.getByText("Failed to load cost data")).toBeInTheDocument();
  });
});
