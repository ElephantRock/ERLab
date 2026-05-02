import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "@/pages/dashboard";
import type {
  SystemStatus,
  IdeaListResponse,
  IdeaSummary,
  PipelineRunSummary,
} from "@/api/types";

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

// ── Mock lazy-loaded charts to avoid recharts canvas issues ─────
vi.mock("@/components/charts/score-distribution", () => ({
  ScoreDistributionChart: () => <div data-testid="score-chart" />,
}));
vi.mock("@/components/charts/domain-breakdown", () => ({
  DomainBreakdownChart: () => <div data-testid="domain-chart" />,
}));
vi.mock("@/components/charts/run-status-chart", () => ({
  RunStatusChart: () => <div data-testid="status-chart" />,
}));

// ── Mock RunCard to avoid complex child dependencies ─────────────
vi.mock("@/components/pipeline/run-card", () => ({
  RunCard: ({ run }: { run: PipelineRunSummary }) => (
    <div data-testid="run-card">{run.domain}</div>
  ),
}));

import { getSystemStatus } from "@/api/status";
import { listRuns } from "@/api/pipeline";
import { listIdeas } from "@/api/ideas";

// ── Helpers ──────────────────────────────────────────────────────
const mockedGetSystemStatus = vi.mocked(getSystemStatus);
const mockedListRuns = vi.mocked(listRuns);
const mockedListIdeas = vi.mocked(listIdeas);

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

function renderDashboard() {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const sampleStatus: SystemStatus = {
  app_name: "Elephant Rock",
  version: "1.0.0",
  config: {},
  defaults: {},
};

const sampleIdea: IdeaSummary = {
  id: 1,
  title: "Cross-lingual Transfer",
  domain: "NLP",
  novelty_score: 0.85,
  feasibility_score: 7,
  overall_score: 0.78,
  pipeline_run_id: null,
  created_at: "2026-05-01T00:00:00Z",
};

const sampleRun: PipelineRunSummary = {
  id: 1,
  status: "completed",
  domain: "NLP",
  current_stage: null,
  ideas_count: 3,
  created_at: "2026-05-01T00:00:00Z",
  completed_at: "2026-05-01T01:00:00Z",
  error_message: null,
};

beforeEach(() => {
  vi.clearAllMocks();
});

// ── TEST-11-01-01: Renders without crashing ──────────────────────
describe("Dashboard", () => {
  it("TEST-11-01-01: renders without crashing", async () => {
    mockedGetSystemStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });

    renderDashboard();

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Overview of your research pipeline.")).toBeInTheDocument();
  });

  // ── TEST-11-01-02: Shows loading state ──────────────────────────
  it("TEST-11-01-02: shows loading state", async () => {
    // Return promises that never resolve to keep loading state
    mockedGetSystemStatus.mockReturnValue(new Promise(() => {}));
    mockedListRuns.mockReturnValue(new Promise(() => {}));
    mockedListIdeas.mockReturnValue(new Promise(() => {}));

    renderDashboard();

    // Skeletons should be visible for the three stat cards
    expect(screen.getByText("Total Runs")).toBeInTheDocument();
    expect(screen.getByText("Total Ideas")).toBeInTheDocument();
    expect(screen.getByText("System")).toBeInTheDocument();
  });

  // ── TEST-11-01-03: Shows empty state ────────────────────────────
  it("TEST-11-01-03: shows empty state when no data", async () => {
    mockedGetSystemStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("No runs yet. Start your first pipeline!")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("No ideas generated yet.")).toBeInTheDocument();
    });
  });

  // ── TEST-11-01-04: Shows populated state (mocked) ───────────────
  it("TEST-11-01-04: shows populated state with mocked data", async () => {
    mockedGetSystemStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [sampleRun], total: 1 });
    mockedListIdeas.mockResolvedValue({
      ideas: [sampleIdea],
      total: 1,
      score_guide: {},
    });

    renderDashboard();

    // Stat cards — use getAllByText since both Runs and Ideas show "1"
    await waitFor(() => {
      const ones = screen.getAllByText("1");
      expect(ones.length).toBeGreaterThanOrEqual(2); // Total Runs + Total Ideas
    });
    await waitFor(() => {
      expect(screen.getByText("Elephant Rock")).toBeInTheDocument();
    });

    // Recent runs section shows run card
    await waitFor(() => {
      expect(screen.getByTestId("run-card")).toBeInTheDocument();
    });

    // Recent ideas section shows idea card
    await waitFor(() => {
      expect(screen.getByText("Cross-lingual Transfer")).toBeInTheDocument();
    });
  });

  // ── TEST-11-01-05: Handles API error ────────────────────────────
  it("TEST-11-01-05: handles API error gracefully", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    mockedGetSystemStatus.mockRejectedValue(new Error("Network error"));
    mockedListRuns.mockRejectedValue(new Error("Network error"));
    mockedListIdeas.mockRejectedValue(new Error("Network error"));

    renderDashboard();

    // The page should still render the header even when APIs fail
    expect(screen.getByText("Dashboard")).toBeInTheDocument();

    // After error, the QueryClient will show 0 counts (from ?? 0 fallbacks)
    await waitFor(() => {
      expect(screen.getByText("No runs yet. Start your first pipeline!")).toBeInTheDocument();
    });

    consoleSpy.mockRestore();
  });
});
