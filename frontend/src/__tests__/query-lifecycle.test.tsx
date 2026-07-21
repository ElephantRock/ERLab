/**
 * F1.3 — Query lifecycle adversarial tests.
 *
 * Proves that read failures remain visible as failures, not swallowed into
 * empty arrays or calm default states. Covers the key invariant from the
 * directive:
 *
 *   failure represented as empty success       0
 *   contract failure represented as empty      0
 *   independent dashboard resources collapsed   0
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import React from "react";

// ── Test helpers ─────────────────────────────────────────────────────

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function renderWithProviders(ui: React.ReactElement) {
  const qc = makeQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

// ── Dashboard lifecycle tests (H-1/H-2) ──────────────────────────────

vi.mock("@/api/pipeline", () => ({
  listRuns: vi.fn(),
}));
vi.mock("@/api/ideas", () => ({
  listIdeas: vi.fn(),
}));
vi.mock("@/api/governance", () => ({
  getPending: vi.fn(),
}));
vi.mock("@/api/ops", () => ({
  getOpsDashboard: vi.fn(),
}));

import { listRuns } from "@/api/pipeline";
import { listIdeas } from "@/api/ideas";
import { getPending } from "@/api/governance";
import { getOpsDashboard } from "@/api/ops";
import Dashboard from "@/pages/dashboard";

describe("Dashboard lifecycle (F1.3.2)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("all four resources succeed — dashboard renders real data", async () => {
    vi.mocked(listRuns).mockResolvedValue({ runs: [], total: 0 });
    vi.mocked(listIdeas).mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    vi.mocked(getPending).mockResolvedValue({ pending: [] });
    vi.mocked(getOpsDashboard).mockResolvedValue({
      health: { total_runs: 0, completed: 0, failed: 0, cancelled: 0, running: 0, pending: 0, average_duration_s: 0, slowest_stages: [] },
      quality_trends: { common_failures: [] },
      costs: { total_cost: 0, by_provider: [], by_stage: [], by_model: [] },
      ideas: { total: 0, cited: 0, supporting: 0 },
    } as any);

    renderWithProviders(<Dashboard />);

    // Quick-start renders when no active run (successful empty)
    await waitFor(() => {
      expect(screen.getByTestId("quick-start")).toBeInTheDocument();
    });
    // No error widgets when all succeed
    expect(screen.queryAllByTestId("widget-error")).toHaveLength(0);
  });

  it("one resource fails while three remain visible — failure does NOT erase success", async () => {
    vi.mocked(listRuns).mockResolvedValue({ runs: [], total: 0 });
    vi.mocked(listIdeas).mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    vi.mocked(getPending).mockRejectedValue(new Error("Network"));
    vi.mocked(getOpsDashboard).mockResolvedValue({
      health: { total_runs: 0, completed: 0, failed: 0, cancelled: 0, running: 0, pending: 0, average_duration_s: 0, slowest_stages: [] },
      quality_trends: { common_failures: [] },
      costs: { total_cost: 0, by_provider: [], by_stage: [], by_model: [] },
      ideas: { total: 0, cited: 0, supporting: 0 },
    } as any);

    renderWithProviders(<Dashboard />);

    // Governance widget shows error
    await waitFor(() => {
      const errors = screen.getAllByTestId("widget-error");
      expect(errors.length).toBeGreaterThanOrEqual(1);
    });

    // Other widgets still render (quick-start = runs succeeded with empty)
    expect(screen.getByTestId("quick-start")).toBeInTheDocument();
  });

  it("all four resources fail — dashboard shows failures, not calm empty state", async () => {
    vi.mocked(listRuns).mockRejectedValue(new Error("Network"));
    vi.mocked(listIdeas).mockRejectedValue(new Error("Network"));
    vi.mocked(getPending).mockRejectedValue(new Error("Network"));
    vi.mocked(getOpsDashboard).mockRejectedValue(new Error("Network"));

    renderWithProviders(<Dashboard />);

    // Multiple error widgets appear (not a calm dashboard)
    await waitFor(() => {
      const errors = screen.getAllByTestId("widget-error");
      expect(errors.length).toBeGreaterThanOrEqual(3);
    });

    // Quick-start does NOT appear (runs failed, not empty)
    expect(screen.queryByTestId("quick-start")).not.toBeInTheDocument();
  });

  it("failed resource is NOT rendered as zero count or empty success", async () => {
    vi.mocked(listRuns).mockResolvedValue({ runs: [], total: 0 });
    vi.mocked(listIdeas).mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    vi.mocked(getPending).mockRejectedValue(new Error("Network"));
    vi.mocked(getOpsDashboard).mockResolvedValue({
      health: { total_runs: 0, completed: 0, failed: 0, cancelled: 0, running: 0, pending: 0, average_duration_s: 0, slowest_stages: [] },
      quality_trends: { common_failures: [] },
      costs: { total_cost: 0, by_provider: [], by_stage: [], by_model: [] },
      ideas: { total: 0, cited: 0, supporting: 0 },
    } as any);

    renderWithProviders(<Dashboard />);

    await waitFor(() => {
      expect(screen.getAllByTestId("widget-error").length).toBeGreaterThanOrEqual(1);
    });

    // The failed governance widget shows "Failed to load" text, not "0" count
    const errorWidget = screen.getAllByTestId("widget-error")[0];
    expect(errorWidget.textContent).toContain("Failed");
  });
});
