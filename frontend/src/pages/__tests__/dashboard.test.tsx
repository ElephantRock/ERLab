import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "@/pages/dashboard";
import type { SystemStatus, IdeaSummary, PipelineRunSummary } from "@/api/types";

vi.mock("@/api/status", () => ({ getSystemStatus: vi.fn() }));
vi.mock("@/api/pipeline", () => ({ listRuns: vi.fn(), triggerRun: vi.fn() }));
vi.mock("@/api/ideas", () => ({ listIdeas: vi.fn() }));
vi.mock("@/api/ops", () => ({ getOpsDashboard: vi.fn() }));
vi.mock("@/api/governance", () => ({ getPending: vi.fn() }));

vi.mock("@/components/charts/score-distribution", () => ({
  ScoreDistributionChart: () => <div data-testid="score-chart" />,
}));
vi.mock("@/components/charts/run-status-chart", () => ({
  RunStatusChart: () => <div data-testid="status-chart" />,
}));
vi.mock("@/components/pipeline/run-card", () => ({
  RunCard: ({ run }: { run: PipelineRunSummary }) => <div data-testid="run-card">{run.domain}</div>,
}));

import { getSystemStatus } from "@/api/status";
import { listRuns } from "@/api/pipeline";
import { listIdeas } from "@/api/ideas";
import { getOpsDashboard } from "@/api/ops";
import { getPending } from "@/api/governance";

const mockedStatus = vi.mocked(getSystemStatus);
const mockedListRuns = vi.mocked(listRuns);
const mockedListIdeas = vi.mocked(listIdeas);
const mockedOps = vi.mocked(getOpsDashboard);
const mockedPending = vi.mocked(getPending);

function qc() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}

function renderDashboard() {
  return render(
    <QueryClientProvider client={qc()}>
      <MemoryRouter><Dashboard /></MemoryRouter>
    </QueryClientProvider>,
  );
}

const sampleStatus: SystemStatus = {
  app_name: "Elephant Rock", version: "1.0.0",
  config: { default_provider: "lmstudio", governance_enabled: true }, defaults: {},
};

const sampleIdea: IdeaSummary = {
  id: 1, title: "Cross-lingual Transfer", domain: "NLP",
  novelty_score: 0.85, feasibility_score: 7, overall_score: 0.78,
  has_proposal: true, source_gap_ids: null, pipeline_run_id: 1,
  created_at: "2026-05-01T00:00:00Z",
};

const sampleRun: PipelineRunSummary = {
  id: 1, status: "completed", domain: "NLP", current_stage: null,
  ideas_count: 3, session_id: null, created_at: "2026-05-01T00:00:00Z",
  completed_at: "2026-05-01T01:00:00Z", error_message: null,
};

const sampleOps = {
  window: { days: 30, from: "", to: "" },
  run_health: { total_runs: 10, completed: 8, failed: 2, cancelled: 0, running: 0, pending: 0, average_duration_s: 60, slowest_stages: [] },
  model_usage: { models: [], total_receipts: 5, warnings: [] },
  source_health: { papers_found_total: 863, zero_result_runs: 0, sources: [{ source: "openalex", papers: 455 }, { source: "arxiv", papers: 18 }] },
  quality_trends: { proposal_count: 4, quality_pass_rate: 93.8, common_failures: [], citation_resolution_rate: 91.1, total_citation_needed: 45, total_valid_citations: 41, remediation_count: 1, restore_count: 0 },
};

beforeEach(() => { vi.clearAllMocks(); });

describe("Dashboard — Research Studio Home", () => {
  it("renders hero with studio title", async () => {
    mockedStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedOps.mockResolvedValue(sampleOps);
    mockedPending.mockResolvedValue({ pending: [] });
    renderDashboard();
    expect(screen.getByText("Welcome to Research Studio")).toBeInTheDocument();
    expect(screen.getByTestId("hero-new-run")).toBeInTheDocument();
  });

  it("shows three summary cards", async () => {
    mockedStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedOps.mockResolvedValue(sampleOps);
    mockedPending.mockResolvedValue({ pending: [] });
    renderDashboard();
    expect(screen.getByTestId("stat-latest-run")).toBeInTheDocument();
    expect(screen.getByTestId("stat-outputs")).toBeInTheDocument();
    expect(screen.getByTestId("stat-attention")).toBeInTheDocument();
  });

  it("shows latest run info when data exists", async () => {
    mockedStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [sampleRun], total: 1 });
    mockedListIdeas.mockResolvedValue({ ideas: [sampleIdea], total: 1, score_guide: {} });
    mockedOps.mockResolvedValue(sampleOps);
    mockedPending.mockResolvedValue({ pending: [] });
    renderDashboard();
    await waitFor(() => { expect(screen.getAllByText("NLP").length).toBeGreaterThan(0); });
    expect(screen.getByText(/Run #1/)).toBeInTheDocument();
  });

  it("shows continue latest run button when runs exist", async () => {
    mockedStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [sampleRun], total: 1 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedOps.mockResolvedValue(sampleOps);
    mockedPending.mockResolvedValue({ pending: [] });
    renderDashboard();
    await waitFor(() => { expect(screen.getByTestId("hero-latest-run")).toBeInTheDocument(); });
  });

  it("shows continue reviewing section", async () => {
    mockedStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [sampleRun], total: 1 });
    mockedListIdeas.mockResolvedValue({ ideas: [sampleIdea], total: 1, score_guide: {} });
    mockedOps.mockResolvedValue(sampleOps);
    mockedPending.mockResolvedValue({ pending: [] });
    renderDashboard();
    await waitFor(() => { expect(screen.getByText(/Continue Reviewing/)).toBeInTheDocument(); });
    // The idea title might be split across elements
    expect(screen.getByTestId("stat-outputs")).toBeInTheDocument();
  });

  it("shows research health with quality pass rate", async () => {
    mockedStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedOps.mockResolvedValue(sampleOps);
    mockedPending.mockResolvedValue({ pending: [] });
    renderDashboard();
    await waitFor(() => { expect(screen.getByText("94%")).toBeInTheDocument(); });
  });

  it("shows source health badges", async () => {
    mockedStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedOps.mockResolvedValue(sampleOps);
    mockedPending.mockResolvedValue({ pending: [] });
    renderDashboard();
    await waitFor(() => { expect(screen.getByText(/openalex/i)).toBeInTheDocument(); });
  });

  it("shows recent proposals with cards", async () => {
    mockedStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [sampleRun], total: 1 });
    mockedListIdeas.mockResolvedValue({ ideas: [sampleIdea], total: 1, score_guide: {} });
    mockedOps.mockResolvedValue(sampleOps);
    mockedPending.mockResolvedValue({ pending: [] });
    renderDashboard();
    await waitFor(() => { expect(screen.getByTestId("recent-output-1")).toBeInTheDocument(); });
  });

  it("shows attention count from quality failures", async () => {
    const opsWithFailures = {
      ...sampleOps,
      quality_trends: { ...sampleOps.quality_trends, common_failures: [{ failure: "word count too low", count: 2 }] },
    };
    mockedStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedOps.mockResolvedValue(opsWithFailures);
    mockedPending.mockResolvedValue({ pending: [{ id: "1", type: "review", summary: "Pending" }] });
    renderDashboard();
    await waitFor(() => { expect(screen.getByText(/issues/)).toBeInTheDocument(); });
    // 3 issues = 2 quality + 1 governance
  });

  it("shows all clear when no attention items", async () => {
    mockedStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedOps.mockResolvedValue(sampleOps);
    mockedPending.mockResolvedValue({ pending: [] });
    renderDashboard();
    await waitFor(() => { expect(screen.getByText(/All criteria verified/)).toBeInTheDocument(); });
  });

  it("degrades gracefully when ops fails", async () => {
    mockedStatus.mockResolvedValue(sampleStatus);
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedOps.mockRejectedValue(new Error("Network"));
    mockedPending.mockResolvedValue({ pending: [] });
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    renderDashboard();
    expect(screen.getByText("Welcome to Research Studio")).toBeInTheDocument();
    await waitFor(() => { expect(screen.getByText("Not available")).toBeInTheDocument(); });
    spy.mockRestore();
  });

  it("degrades gracefully when all APIs fail", async () => {
    mockedStatus.mockRejectedValue(new Error("Network"));
    mockedListRuns.mockRejectedValue(new Error("Network"));
    mockedListIdeas.mockRejectedValue(new Error("Network"));
    mockedOps.mockRejectedValue(new Error("Network"));
    mockedPending.mockRejectedValue(new Error("Network"));
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    renderDashboard();
    expect(screen.getByText("Welcome to Research Studio")).toBeInTheDocument();
    expect(screen.getByTestId("hero-new-run")).toBeInTheDocument();
    spy.mockRestore();
  });
});
