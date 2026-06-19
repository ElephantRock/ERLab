/** Tests for BATCH-32 TASK-02: lazy loading + pagination. */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

// ── JSDOM polyfills for Radix UI ─────────────────────────────────
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;

class IntersectionObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.IntersectionObserver = IntersectionObserverMock as unknown as typeof IntersectionObserver;

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// ── Mock API modules (AR-03: no real HTTP) ──────────────────────
vi.mock("@/api/status", () => ({
  getSystemStatus: vi.fn(),
}));
vi.mock("@/api/pipeline", () => ({
  listRuns: vi.fn(),
  triggerRun: vi.fn(),
}));
vi.mock("@/api/ideas", () => ({
  listIdeas: vi.fn(),
}));
vi.mock("@/api/gaps", () => ({
  listGaps: vi.fn(),
}));
vi.mock("@/api/ops", () => ({
  getOpsDashboard: vi.fn(),
}));
vi.mock("@/api/governance", () => ({
  getPending: vi.fn(),
}));

// ── Mock lazy-loaded charts ──────────────────────────────────────
vi.mock("@/components/charts/score-distribution", () => ({
  ScoreDistributionChart: () => <div data-testid="score-chart" />,
}));
vi.mock("@/components/charts/domain-breakdown", () => ({
  DomainBreakdownChart: () => <div data-testid="domain-chart" />,
}));
vi.mock("@/components/charts/run-status-chart", () => ({
  RunStatusChart: () => <div data-testid="status-chart" />,
}));

vi.mock("@/components/pipeline/run-card", () => ({
  RunCard: ({ run }: { run: { domain: string } }) => (
    <div data-testid="run-card">{run.domain}</div>
  ),
}));

vi.mock("@/components/gaps/gap-card", () => ({
  GapCard: ({ gap }: { gap: { id: number; title: string } }) => (
    <div data-testid="gap-card">{gap.title}</div>
  ),
}));

vi.mock("@/components/ideas/idea-card", () => ({
  IdeaCard: ({ idea }: { idea: { id: number; title: string } }) => (
    <div data-testid="idea-card">{idea.title}</div>
  ),
}));

import { getSystemStatus } from "@/api/status";
import { listRuns } from "@/api/pipeline";
import { listIdeas } from "@/api/ideas";
import { listGaps } from "@/api/gaps";
import { getOpsDashboard } from "@/api/ops";
import { getPending } from "@/api/governance";

const mockedGetSystemStatus = vi.mocked(getSystemStatus);
const mockedListRuns = vi.mocked(listRuns);
const mockedListIdeas = vi.mocked(listIdeas);
const mockedListGaps = vi.mocked(listGaps);
const mockedGetOps = vi.mocked(getOpsDashboard);
const mockedGetPending = vi.mocked(getPending);

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

// ── Shared mock data ─────────────────────────────────────────────

const sampleStatus = {
  app_name: "Elephant Rock",
  version: "1.0.0",
  config: {},
  defaults: {},
};

function makeIdea(id: number) {
  return {
    id,
    title: `Idea ${id}`,
    domain: "NLP",
    novelty_score: 0.8,
    feasibility_score: 7,
    overall_score: 0.75,
    source_gap_ids: null,
    has_proposal: false,
    pipeline_run_id: null,
    created_at: "2026-05-01T00:00:00Z",
  };
}

function makeGap(id: number, confidence = 0.8) {
  return {
    id,
    title: `Gap ${id}`,
    description: `Description ${id}`,
    gap_type: "methodological",
    confidence,
    potential_impact: "High",
    idea_count: 0,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ═══════════════════════════════════════════════════════════════════
// TEST-32-02-01: Dashboard lazy loads chart components
// ═══════════════════════════════════════════════════════════════════

describe("TEST-32-02-01: Dashboard lazy loads chart components", () => {
  it("renders chart placeholders via lazy-loaded components", async () => {
    // Import Dashboard dynamically to test lazy loading
    const Dashboard = (await import("@/pages/dashboard")).default;

    mockedGetSystemStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({
      runs: [
        {
          id: 1,
          status: "completed",
          domain: "NLP",
          current_stage: null,
          ideas_count: 3,
          session_id: null,
          created_at: "2026-05-01T00:00:00Z",
          completed_at: "2026-05-01T01:00:00Z",
          error_message: null,
        },
      ],
      total: 1,
    });
    mockedListIdeas.mockResolvedValue({
      ideas: [makeIdea(1)],
      total: 1,
      score_guide: {},
    });
    mockedGetOps.mockResolvedValue({
      window: { days: 30, from: "", to: "" },
      run_health: { total_runs: 1, completed: 1, failed: 0, cancelled: 0, running: 0, pending: 0, average_duration_s: 60, slowest_stages: [] },
      model_usage: { models: [], total_receipts: 0, warnings: [] },
      source_health: { papers_found_total: 0, zero_result_runs: 0, sources: [] },
      quality_trends: { proposal_count: 0, quality_pass_rate: 100, common_failures: [], citation_resolution_rate: null, total_citation_needed: 0, total_valid_citations: 0, remediation_count: 0, restore_count: 0 },
    });
    mockedGetPending.mockResolvedValue({ pending: [] });

    const qc = createQueryClient();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // The chart section should render when data exists
    await waitFor(() => {
      expect(screen.getByText("Analytics")).toBeInTheDocument();
    });

    // Lazy-loaded chart components render their mock placeholders
    expect(screen.getByTestId("score-chart")).toBeInTheDocument();
    expect(screen.getByTestId("status-chart")).toBeInTheDocument();
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST-32-02-02: Gaps explorer paginates results
// ═══════════════════════════════════════════════════════════════════

describe("TEST-32-02-02: Gaps explorer paginates results", () => {
  it("passes offset to listGaps for page changes", async () => {
    const GapsExplorer = (await import("@/pages/gaps-explorer")).default;

    const manyGaps = Array.from({ length: 25 }, (_, i) => makeGap(i + 1));
    mockedListGaps.mockResolvedValue({ gaps: manyGaps.slice(0, 20), total: 25 });

    const qc = createQueryClient();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <GapsExplorer />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText(/25 gap/)).toBeInTheDocument();
    });

    // First call should use offset=0
    expect(mockedListGaps).toHaveBeenCalledWith(
      expect.objectContaining({ offset: 0, limit: 20 }),
    );
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST-32-02-03: Ideas browser paginates results
// ═══════════════════════════════════════════════════════════════════

describe("TEST-32-02-03: Ideas browser paginates results", () => {
  it("passes offset to listIdeas for page changes", async () => {
    const IdeasBrowser = (await import("@/pages/ideas-browser")).default;

    const manyIdeas = Array.from({ length: 25 }, (_, i) => makeIdea(i + 1));
    mockedListIdeas.mockResolvedValue({
      ideas: manyIdeas.slice(0, 20),
      total: 25,
      score_guide: {},
    });

    const qc = createQueryClient();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <IdeasBrowser />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText(/25 research ideas generated/)).toBeInTheDocument();
    });

    // First call should use offset=0
    expect(mockedListIdeas).toHaveBeenCalledWith(
      expect.objectContaining({ offset: 0, limit: 20 }),
    );
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST-32-02-04: Pagination controls work (next/prev)
// ═══════════════════════════════════════════════════════════════════

describe("TEST-32-02-04: Pagination controls work (next/prev)", () => {
  it("clicking Next advances the page and Previous goes back", async () => {
    const IdeasBrowser = (await import("@/pages/ideas-browser")).default;

    // 45 ideas → 3 pages of 20; dynamic mock based on offset
    mockedListIdeas.mockImplementation((params) =>
      Promise.resolve({
        ideas: Array.from({ length: Math.min(20, 45 - (params?.offset ?? 0)) }, (_, i) =>
          makeIdea(i + 1 + (params?.offset ?? 0))
        ),
        total: 45,
        score_guide: {},
      })
    );

    const qc = createQueryClient();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <IdeasBrowser />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // Wait for page 1 to render
    await waitFor(() => {
      expect(screen.getByText(/Page 1 of 3/)).toBeInTheDocument();
    });

    // Click Next
    const nextBtn = screen.getByText("Next");
    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(mockedListIdeas).toHaveBeenCalledWith(
        expect.objectContaining({ offset: 20 }),
      );
    });

    // Wait for page 2 to render before clicking Previous
    await waitFor(() => {
      expect(screen.getByText(/Page 2 of 3/)).toBeInTheDocument();
    });

    // Click Previous
    const prevBtn = screen.getByRole("button", { name: /previous/i });
    fireEvent.click(prevBtn);

    await waitFor(() => {
      expect(mockedListIdeas).toHaveBeenCalledWith(
        expect.objectContaining({ offset: 0 }),
      );
    });
  });
});
