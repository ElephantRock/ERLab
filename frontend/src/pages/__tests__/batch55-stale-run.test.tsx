import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import RunDetail from "@/pages/run-detail";
import type { PipelineRunDetail, IdeaSummary } from "@/api/types";

// ── Mock API modules ────────────────────────────────────────────
vi.mock("@/api/pipeline", () => ({
  getRunDetail: vi.fn(),
  getRunIdeas: vi.fn(),
}));

vi.mock("@/components/charts/score-distribution", () => ({}));
vi.mock("@/components/charts/domain-breakdown", () => ({}));
vi.mock("@/components/charts/run-status-chart", () => ({}));

import { getRunDetail, getRunIdeas } from "@/api/pipeline";

const mockedGetRunDetail = vi.mocked(getRunDetail);
const mockedGetRunIdeas = vi.mocked(getRunIdeas);

// ── Helpers ──────────────────────────────────────────────────────

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

function renderRunDetail(runId: string = "1") {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/runs/${runId}`]}>
        <Routes>
          <Route path="/runs/:id" element={<RunDetail />} />
          <Route path="/" element={<div data-testid="dashboard">Dashboard</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ── Stale run: created more than 5 minutes ago, status "running" ──
function makeStaleRunningRun(): PipelineRunDetail {
  const sixMinutesAgo = new Date(Date.now() - 6 * 60 * 1000).toISOString();
  return {
    id: 42,
    status: "running",
    domain: "AI/NLP",
    current_stage: "gap_analysis",
    ideas_count: 0,
    created_at: sixMinutesAgo,
    completed_at: null,
    error_message: null,
    config: {},
    stages_completed: ["literature_search", "ingestion"],
  };
}

// ── Completed run ──
function makeCompletedRun(): PipelineRunDetail {
  return {
    id: 1,
    status: "completed",
    domain: "AI/NLP",
    current_stage: null,
    ideas_count: 2,
    created_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
    error_message: null,
    config: {},
    stages_completed: [
      "literature_search",
      "ingestion",
      "gap_analysis",
      "idea_generation",
      "novelty_checking",
      "feasibility_scoring",
      "proposal_synthesis",
      "export",
    ],
  };
}

describe("BATCH-55: Stale Run Detector", () => {
  it("TEST-55-03-01: shows warning for run in 'running' status older than 5 minutes", async () => {
    mockedGetRunDetail.mockResolvedValue(makeStaleRunningRun());
    mockedGetRunIdeas.mockResolvedValue({ ideas: [], total: 0 });

    renderRunDetail("42");

    await waitFor(() => {
      expect(screen.getByTestId("run-detail")).toBeInTheDocument();
    });

    // The stale warning should appear
    expect(screen.getByTestId("stale-run-warning")).toBeInTheDocument();
    expect(
      screen.getByText(/running for over 5 minutes/i),
    ).toBeInTheDocument();
  });

  it("TEST-55-03-02: does not show warning for completed runs", async () => {
    mockedGetRunDetail.mockResolvedValue(makeCompletedRun());
    mockedGetRunIdeas.mockResolvedValue({ ideas: [], total: 0 });

    renderRunDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("run-detail")).toBeInTheDocument();
    });

    // No stale warning for completed runs
    expect(screen.queryByTestId("stale-run-warning")).not.toBeInTheDocument();
  });
});
