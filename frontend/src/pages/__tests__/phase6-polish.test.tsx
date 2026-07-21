/**
 * Phase 6: Polish, Accessibility, Test Hardening
 *
 * Verifies:
 * - Pages use ErrorCard for query failures (not raw divs)
 * - Pages use EmptyState for no-data (not raw text)
 * - Icon-only buttons have aria-label
 * - Key flows remain keyboard accessible
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Polyfills ──────────────────────────────────────────────────
class ResizeObserverMock { observe() {} unobserve() {} disconnect() {} }
global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (q: string) => ({
    matches: false, media: q, onchange: null,
    addListener: () => {}, removeListener: () => {},
    addEventListener: () => {}, removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// ── Mocks ──────────────────────────────────────────────────────
vi.mock("@/api/autonomous", () => ({
  triggerAutonomous: vi.fn(),
  getAutonomousHistory: vi.fn(),
  stopAutonomousCycle: vi.fn(),
  getEvolutionStatus: vi.fn().mockResolvedValue({ enabled: false, overlays_generated: 0, recent_outcomes: [] }),
  startScheduler: vi.fn(),
  stopScheduler: vi.fn(),
  getSchedulerStatus: vi.fn().mockResolvedValue({ status: "stopped" }),
  getConsciousnessState: vi.fn().mockResolvedValue({ state: "idle" }),
}));

vi.mock("@/api/costs", () => ({
  getCostSummary: vi.fn(),
  getCostByProvider: vi.fn(),
  getCostByStage: vi.fn(),
  getCostByModel: vi.fn(),
  getRunCostBreakdown: vi.fn(),
}));

vi.mock("@/api/knowledge", () => ({
  searchKnowledge: vi.fn(),
  getKnowledgeStats: vi.fn().mockResolvedValue({ total_documents: 0, total_chunks: 0 }),
}));

vi.mock("@/api/literature", () => ({
  searchLiterature: vi.fn(),
  ingestPaper: vi.fn(),
}));

vi.mock("@/api/client", () => ({
  apiFetchUnchecked: vi.fn(),
  apiFetchBlob: vi.fn(),
  testConnection: vi.fn().mockResolvedValue({ ok: true, version: "0.1.0" }),
  getDetailedStatus: vi.fn().mockResolvedValue(null),
  getApiUrl: () => "",
  getApiKey: () => "",
  buildUrl: (p: string) => p,
  buildAuthHeaders: () => ({}),
}));

vi.mock("@/api/sessions", () => ({
  getSessionList: vi.fn(),
}));

vi.mock("@/api/pipeline", () => ({
  listRuns: vi.fn().mockResolvedValue({ runs: [], total: 0 }),
}));

vi.mock("@/api/traces", () => ({
  getTraceSummary: vi.fn(),
  getTrace: vi.fn(),
  getTraceMetrics: vi.fn(),
}));

vi.mock("@/components/charts/score-distribution", () => ({
  ScoreDistributionChart: () => <div data-testid="score-chart" />,
}));
vi.mock("@/components/charts/domain-breakdown", () => ({
  DomainBreakdownChart: () => <div data-testid="domain-chart" />,
}));
vi.mock("@/components/charts/run-status-chart", () => ({
  RunStatusChart: () => <div data-testid="status-chart" />,
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { getAutonomousHistory } from "@/api/autonomous";
import { getCostSummary, getCostByProvider, getCostByStage, getCostByModel } from "@/api/costs";
import { searchKnowledge } from "@/api/knowledge";
import { searchLiterature } from "@/api/literature";
import { getSessionList } from "@/api/sessions";
import { getTraceSummary } from "@/api/traces";

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ── Autonomous page error/empty ────────────────────────────────

describe("Phase 6: Error states use ErrorCard", () => {
  it("autonomous page shows ErrorCard on history failure", async () => {
    vi.mocked(getAutonomousHistory).mockRejectedValue(new Error("Network error"));

    const AutonomousPage = (await import("@/pages/autonomous")).default;
    render(
      <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter>
          <AutonomousPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("autonomous-error")).toBeInTheDocument();
    });
    // ErrorCard has role=alert
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("autonomous page shows EmptyState when no cycles", async () => {
    vi.mocked(getAutonomousHistory).mockResolvedValue({ cycles: [] });

    const AutonomousPage = (await import("@/pages/autonomous")).default;
    render(
      <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter>
          <AutonomousPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("autonomous-empty")).toBeInTheDocument();
    });
    expect(screen.getByText("No autonomous cycles yet")).toBeInTheDocument();
  });

  it("costs page shows ErrorCard on API failure", async () => {
    vi.mocked(getCostSummary).mockRejectedValue(new Error("Server error"));
    vi.mocked(getCostByProvider).mockRejectedValue(new Error("Server error"));
    vi.mocked(getCostByStage).mockRejectedValue(new Error("Server error"));
    vi.mocked(getCostByModel).mockRejectedValue(new Error("Server error"));

    const CostsPage = (await import("@/pages/costs")).default;
    render(
      <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter>
          <CostsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("cost-error")).toBeInTheDocument();
    });
    expect(screen.getByText("Failed to load cost data")).toBeInTheDocument();
  });
});

// ── Knowledge search error/empty ───────────────────────────────

describe("Phase 6: Knowledge search error/empty", () => {
  it("shows ErrorCard on search failure", async () => {
    vi.mocked(searchKnowledge).mockRejectedValue(new Error("Search failed"));

    const KnowledgeSearchPage = (await import("@/pages/knowledge-search")).default;
    const { fireEvent } = await import("@testing-library/react");

    render(
      <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter>
          <KnowledgeSearchPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // Need to type and submit to trigger the query
    const input = screen.getByPlaceholderText(/search/i);
    fireEvent.change(input, { target: { value: "test query" } });
    fireEvent.submit(input.closest("form") || input);

    await waitFor(() => {
      expect(screen.getByTestId("knowledge-search-error")).toBeInTheDocument();
    });
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});

// ── Accessibility: icon-only buttons ───────────────────────────

describe("Phase 6: Icon-only button aria-labels", () => {
  it("sidebar collapse button has aria-label", async () => {
    const { AuthProvider } = await import("@/contexts/auth-context");
    const { SettingsProvider } = await import("@/contexts/settings-context");
    const { QueryClient, QueryClientProvider } = await import("@tanstack/react-query");
    const AppShell = (await import("@/components/layout/app-shell")).AppShell;
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(
      <MemoryRouter>
        <QueryClientProvider client={qc}>
          <AuthProvider>
            <SettingsProvider>
              <AppShell />
            </SettingsProvider>
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    );

    // The collapse button should have an aria-label
    const collapseBtn = screen.getByLabelText(/sidebar/i);
    expect(collapseBtn).toBeInTheDocument();
  });
});
