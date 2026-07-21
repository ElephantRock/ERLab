/**
 * Dashboard tests — Action Queue (Phase 3 rebuild).
 *
 * The old dashboard was a hero + stat cards + charts (Trophy Case).
 * The new dashboard is an action queue: what needs attention right now.
 * These tests verify the new structure, not the old one.
 */

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

import { listRuns } from "@/api/pipeline";
import { listIdeas } from "@/api/ideas";
import { getOpsDashboard } from "@/api/ops";
import { getPending } from "@/api/governance";

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
  window: { days: 7, from: "", to: "" },
  run_health: { total_runs: 10, completed: 8, failed: 2, cancelled: 0, running: 0, pending: 0, average_duration_s: 60, slowest_stages: [] },
  model_usage: { models: [], total_receipts: 5, warnings: [] },
  source_health: { papers_found_total: 863, zero_result_runs: 0, sources: [] },
  quality_trends: { proposal_count: 4, quality_pass_rate: 93.8, common_failures: [], citation_resolution_rate: 91.1, total_citation_needed: 45, total_valid_citations: 41, remediation_count: 1, restore_count: 0, fabrications_currently_present: 0, fabrications_found_total: 0 },
};

beforeEach(() => { vi.clearAllMocks(); });

describe("Dashboard — Action Queue", () => {
  it("renders quick-start card when no active run", async () => {
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedOps.mockResolvedValue(sampleOps);
    mockedPending.mockResolvedValue({ pending: [] });
    renderDashboard();
    expect(await screen.findByTestId("quick-start")).toBeInTheDocument();
    expect(screen.getByTestId("hero-new-run")).toBeInTheDocument();
  });

  it("renders active run card when a run is running", async () => {
    const activeRun = { ...sampleRun, status: "running", current_stage: "synthesizing" };
    mockedListRuns.mockResolvedValue({ runs: [activeRun], total: 1 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedOps.mockResolvedValue(sampleOps);
    mockedPending.mockResolvedValue({ pending: [] });
    renderDashboard();
    expect(await screen.findByTestId("active-run-card")).toBeInTheDocument();
    expect(screen.queryByTestId("quick-start")).not.toBeInTheDocument();
  });

  it("renders recent proposals when ideas exist", async () => {
    mockedListRuns.mockResolvedValue({ runs: [sampleRun], total: 1 });
    mockedListIdeas.mockResolvedValue({ ideas: [sampleIdea], total: 1, score_guide: {} });
    mockedOps.mockResolvedValue(sampleOps);
    mockedPending.mockResolvedValue({ pending: [] });
    renderDashboard();
    await waitFor(() => { expect(screen.getByText("Cross-lingual Transfer")).toBeInTheDocument(); });
  });

  it("shows needs-attention section when quality issues exist", async () => {
    const opsWithFailures = {
      ...sampleOps,
      quality_trends: { ...sampleOps.quality_trends, common_failures: [{ failure: "word count too low", count: 2 }] },
    };
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedOps.mockResolvedValue(opsWithFailures);
    mockedPending.mockResolvedValue({ pending: [{ id: "1", type: "review", summary: "Pending" }] });
    renderDashboard();
    await waitFor(() => { expect(screen.getByTestId("action-governance")).toBeInTheDocument(); });
    expect(screen.getByTestId("action-quality")).toBeInTheDocument();
  });

  it("shows latest run section when no active run", async () => {
    mockedListRuns.mockResolvedValue({ runs: [sampleRun], total: 1 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedOps.mockResolvedValue(sampleOps);
    mockedPending.mockResolvedValue({ pending: [] });
    renderDashboard();
    await waitFor(() => { expect(screen.getByText("Latest Run")).toBeInTheDocument(); });
  });

  it("degrades gracefully when APIs fail — F1.3: failures are visible, not swallowed", async () => {
    mockedListRuns.mockRejectedValue(new Error("Network"));
    mockedListIdeas.mockRejectedValue(new Error("Network"));
    mockedOps.mockRejectedValue(new Error("Network"));
    mockedPending.mockRejectedValue(new Error("Network"));
    renderDashboard();
    // F1.3: each failed resource renders an explicit error widget, NOT an
    // empty-success fallback. The dashboard is degraded but truthful.
    await waitFor(() => {
      const errorWidgets = screen.getAllByTestId("widget-error");
      expect(errorWidgets.length).toBeGreaterThanOrEqual(3);
    });
    // Quick-start card should NOT appear (runs failed, so it shows error not empty)
    expect(screen.queryByTestId("quick-start")).not.toBeInTheDocument();
  });

  it("does NOT render SYS_OK or telemetry headers", async () => {
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedOps.mockResolvedValue(sampleOps);
    mockedPending.mockResolvedValue({ pending: [] });
    const { container } = renderDashboard();
    await waitFor(() => { expect(screen.getByTestId("quick-start")).toBeInTheDocument(); });
    expect(screen.queryByText("SYS_OK")).not.toBeInTheDocument();
    expect(screen.queryByText("Welcome to Research Studio")).not.toBeInTheDocument();
  });

  it("does NOT use sub-micro type (text-[8px], [9px], [10px])", async () => {
    mockedListRuns.mockResolvedValue({ runs: [], total: 0 });
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });
    mockedOps.mockResolvedValue(sampleOps);
    mockedPending.mockResolvedValue({ pending: [] });
    const { container } = renderDashboard();
    await waitFor(() => { expect(screen.getByTestId("quick-start")).toBeInTheDocument(); });
    const html = container.innerHTML;
    expect(html).not.toMatch(/text-\[8px\]/);
    expect(html).not.toMatch(/text-\[9px\]/);
    expect(html).not.toMatch(/text-\[10px\]/);
  });
});
