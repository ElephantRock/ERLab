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

// ── Mock API modules ────────────────────────────────────────────
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

vi.mock("@/api/ops", () => ({
  getOpsDashboard: vi.fn(),
}));

vi.mock("@/api/governance", () => ({
  getPending: vi.fn(),
}));

vi.mock("@/components/charts/score-distribution", () => ({
  ScoreDistributionChart: () => <div data-testid="score-chart" />,
}));
vi.mock("@/components/charts/run-status-chart", () => ({
  RunStatusChart: () => <div data-testid="status-chart" />,
}));

vi.mock("@/components/pipeline/run-card", () => ({
  RunCard: ({ run }: { run: PipelineRunSummary }) => (
    <div data-testid="run-card">{run.domain}</div>
  ),
}));

import { getSystemStatus } from "@/api/status";
import { listRuns } from "@/api/pipeline";
import { listIdeas } from "@/api/ideas";
import { getOpsDashboard } from "@/api/ops";
import { getPending } from "@/api/governance";

const mockedGetSystemStatus = vi.mocked(getSystemStatus);
const mockedListRuns = vi.mocked(listRuns);
const mockedListIdeas = vi.mocked(listIdeas);
const mockedGetOps = vi.mocked(getOpsDashboard);
const mockedGetPending = vi.mocked(getPending);

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
  config: { default_provider: "lmstudio", governance_enabled: true },
  defaults: {},
};

const sampleIdea: IdeaSummary = {
  id: 1,
  title: "Cross-lingual Transfer",
  domain: "NLP",
  novelty_score: 0.85,
  feasibility_score: 7,
  overall_score: 0.78,
  has_proposal: true,
  source_gap_ids: null,
  pipeline_run_id: 1,
  created_at: "2026-05-01T00:00:00Z",
};

const sampleRun: PipelineRunSummary = {
  id: 1,
  status: "completed",
  domain: "NLP",
  current_stage: null,
  ideas_count: 3,
  session_id: null,
  created_at: "2026-05-01T00:00:00Z",
  completed_at: "2026-05-01T01:00:00Z",
  error_message: null,
};

const sampleOps = {
  window: { days: 30, from: "2026-05-19T00:00:00Z", to: "2026-06-18T00:00:00Z" },
  run_health: {
    total_runs: 10,
    completed: 8,
    failed: 2,
    cancelled: 0,
    running: 0,
    pending: 0,
    average_duration_s: 60,
    slowest_stages: [],
  },
  model_usage: { models: [], total_receipts: 5, warnings: [] },
  source_health: { papers_found_total: 863, zero_result_runs: 0, sources: [] },
  quality_trends: {
    proposal_count: 4,
    quality_pass_rate: 93.8,
    common_failures: [],
    citation_resolution_rate: 91.1,
    total_citation_needed: 45,
    total_valid_citations: 41,
    remediation_count: 1,
    restore_count: 0,
  },
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Dashboard — Research Command Center", () => {
  it("renders hero with command center title", async () => {
    mockedGetSystemStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedGetOps.mockResolvedValue(sampleOps);
    mockedGetPending.mockResolvedValue({ pending: [] });

    renderDashboard();

    expect(screen.getByText("Research Command Center")).toBeInTheDocument();
    expect(screen.getByTestId("hero-new-run")).toBeInTheDocument();
  });

  it("shows start new run CTA in hero", async () => {
    mockedGetSystemStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedGetOps.mockResolvedValue(sampleOps);
    mockedGetPending.mockResolvedValue({ pending: [] });

    renderDashboard();

    expect(screen.getByTestId("hero-new-run")).toHaveTextContent("Start New Research Run");
  });

  it("shows open latest run button when runs exist", async () => {
    mockedGetSystemStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [sampleRun], total: 1 });
    mockedListIdeas.mockResolvedValue({ ideas: [sampleIdea], total: 1, score_guide: {} });
    mockedGetOps.mockResolvedValue(sampleOps);
    mockedGetPending.mockResolvedValue({ pending: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByTestId("hero-latest-run")).toBeInTheDocument();
    });
  });

  it("does not show latest run button when no runs", async () => {
    mockedGetSystemStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedGetOps.mockResolvedValue(sampleOps);
    mockedGetPending.mockResolvedValue({ pending: [] });

    renderDashboard();

    expect(screen.queryByTestId("hero-latest-run")).not.toBeInTheDocument();
  });

  it("renders four status summary cards", async () => {
    mockedGetSystemStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedGetOps.mockResolvedValue(sampleOps);
    mockedGetPending.mockResolvedValue({ pending: [] });

    renderDashboard();

    expect(screen.getByTestId("stat-latest-run")).toBeInTheDocument();
    expect(screen.getByTestId("stat-outputs")).toBeInTheDocument();
    expect(screen.getByTestId("stat-quality")).toBeInTheDocument();
    expect(screen.getByTestId("stat-review")).toBeInTheDocument();
  });

  it("shows quality pass rate from ops data", async () => {
    mockedGetSystemStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedGetOps.mockResolvedValue(sampleOps);
    mockedGetPending.mockResolvedValue({ pending: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("94%")).toBeInTheDocument();
    });
  });

  it("shows attention queue with all clear when no issues", async () => {
    mockedGetSystemStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedGetOps.mockResolvedValue(sampleOps);
    mockedGetPending.mockResolvedValue({ pending: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/All clear/)).toBeInTheDocument();
    });
  });

  it("shows attention items for failed runs", async () => {
    const failedRun = { ...sampleRun, status: "failed" as const, error_message: "Timeout" };
    mockedGetSystemStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [failedRun], total: 1 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedGetOps.mockResolvedValue(sampleOps);
    mockedGetPending.mockResolvedValue({ pending: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByTestId("attention-failed_run")).toBeInTheDocument();
    });
  });

  it("shows recent research outputs with idea titles", async () => {
    mockedGetSystemStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [sampleRun], total: 1 });
    mockedListIdeas.mockResolvedValue({ ideas: [sampleIdea], total: 1, score_guide: {} });
    mockedGetOps.mockResolvedValue(sampleOps);
    mockedGetPending.mockResolvedValue({ pending: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("Cross-lingual Transfer")).toBeInTheDocument();
    });
  });

  it("shows system health panel with backend status", async () => {
    mockedGetSystemStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedGetOps.mockResolvedValue(sampleOps);
    mockedGetPending.mockResolvedValue({ pending: [] });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("Backend")).toBeInTheDocument();
      expect(screen.getByText("Online")).toBeInTheDocument();
    });
  });

  it("degrades gracefully when ops dashboard fails", async () => {
    mockedGetSystemStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedGetOps.mockRejectedValue(new Error("Network error"));
    mockedGetPending.mockResolvedValue({ pending: [] });

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    renderDashboard();

    // Page still renders
    expect(screen.getByText("Research Command Center")).toBeInTheDocument();
    // Quality card shows fallback
    await waitFor(() => {
      expect(screen.getByText("No data")).toBeInTheDocument();
    });
    consoleSpy.mockRestore();
  });

  it("degrades gracefully when all APIs fail", async () => {
    mockedGetSystemStatus.mockRejectedValue(new Error("Network error"));
    mockedListRuns.mockRejectedValue(new Error("Network error"));
    mockedListIdeas.mockRejectedValue(new Error("Network error"));
    mockedGetOps.mockRejectedValue(new Error("Network error"));
    mockedGetPending.mockRejectedValue(new Error("Network error"));

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    renderDashboard();

    expect(screen.getByText("Research Command Center")).toBeInTheDocument();
    expect(screen.getByTestId("hero-new-run")).toBeInTheDocument();
    consoleSpy.mockRestore();
  });
});
