import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

const sampleRun: PipelineRunDetail = {
  id: 1,
  status: "completed",
  domain: "AI/NLP",
  current_stage: null,
  ideas_count: 2,
  created_at: "2026-05-01T10:00:00Z",
  completed_at: "2026-05-01T10:05:00Z",
  error_message: null,
  config: {},
  stages_completed: ["literature_search", "ingestion", "gap_analysis", "idea_generation", "novelty_checking", "feasibility_scoring", "proposal_synthesis", "export"],
};

const sampleIdeas: IdeaSummary[] = [
  {
    id: 1,
    title: "Cross-lingual Transfer",
    domain: "NLP",
    novelty_score: 0.85,
    feasibility_score: 7,
    overall_score: 0.78,
    pipeline_run_id: 1,
    created_at: "2026-05-01T00:00:00Z",
  },
  {
    id: 2,
    title: "Few-shot Prompting",
    domain: "NLP",
    novelty_score: 0.7,
    feasibility_score: 8,
    overall_score: 0.75,
    pipeline_run_id: 1,
    created_at: "2026-05-01T00:00:00Z",
  },
];

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

describe("RunDetail (BATCH-12/TASK-03)", () => {
  // ── TEST-12-03-01: Run detail page renders with valid run data ──

  it("TEST-12-03-01: renders with valid run data", async () => {
    mockedGetRunDetail.mockResolvedValue(sampleRun);
    mockedGetRunIdeas.mockResolvedValue({ ideas: sampleIdeas, total: 2 });

    renderRunDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("run-detail")).toBeInTheDocument();
    });
    expect(screen.getByTestId("run-title")).toHaveTextContent("Run #1");
  });

  // ── TEST-12-03-02: Shows run metadata ──

  it("TEST-12-03-02: shows run metadata (ID, domain, status, timestamps)", async () => {
    mockedGetRunDetail.mockResolvedValue(sampleRun);
    mockedGetRunIdeas.mockResolvedValue({ ideas: sampleIdeas, total: 2 });

    renderRunDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("run-metadata")).toBeInTheDocument();
    });

    expect(screen.getByTestId("run-status")).toHaveTextContent("completed");
    expect(screen.getByTestId("run-title")).toHaveTextContent("Run #1");
    expect(screen.getByTestId("run-created-at")).toBeInTheDocument();
    expect(screen.getByTestId("run-completed-at")).toBeInTheDocument();
  });

  // ── TEST-12-03-03: Shows stages timeline with completion status ──

  it("TEST-12-03-03: shows stages timeline with completion status", async () => {
    mockedGetRunDetail.mockResolvedValue(sampleRun);
    mockedGetRunIdeas.mockResolvedValue({ ideas: sampleIdeas, total: 2 });

    renderRunDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("stages-timeline")).toBeInTheDocument();
    });

    // All 8 stages should appear
    expect(screen.getByText("Literature Search")).toBeInTheDocument();
    expect(screen.getByText("PDF Ingestion")).toBeInTheDocument();
    expect(screen.getByText("Gap Analysis")).toBeInTheDocument();
    expect(screen.getByText("Idea Generation")).toBeInTheDocument();
    expect(screen.getByText("Novelty Checking")).toBeInTheDocument();
    expect(screen.getByText("Feasibility Scoring")).toBeInTheDocument();
    expect(screen.getByText("Proposal Synthesis")).toBeInTheDocument();
    expect(screen.getByText("Export")).toBeInTheDocument();
  });

  // ── TEST-12-03-04: Shows generated ideas list ──

  it("TEST-12-03-04: shows generated ideas list", async () => {
    mockedGetRunDetail.mockResolvedValue(sampleRun);
    mockedGetRunIdeas.mockResolvedValue({ ideas: sampleIdeas, total: 2 });

    renderRunDetail("1");

    await waitFor(() => {
      expect(screen.getByText("Cross-lingual Transfer")).toBeInTheDocument();
      expect(screen.getByText("Few-shot Prompting")).toBeInTheDocument();
    });

    expect(screen.getByTestId("ideas-list")).toBeInTheDocument();
  });

  // ── TEST-12-03-05: Shows error message for failed runs ──

  it("TEST-12-03-05: shows error message for failed runs", async () => {
    const failedRun: PipelineRunDetail = {
      ...sampleRun,
      status: "failed",
      error_message: "LLM provider rate limit exceeded",
      completed_at: null,
      stages_completed: ["literature_search", "ingestion"],
      current_stage: "gap_analysis",
    };
    mockedGetRunDetail.mockResolvedValue(failedRun);
    mockedGetRunIdeas.mockResolvedValue({ ideas: [], total: 0 });

    renderRunDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("error-message")).toBeInTheDocument();
    });

    expect(screen.getByText("LLM provider rate limit exceeded")).toBeInTheDocument();
  });

  // ── TEST-12-03-06: Resume button appears only for failed runs ──

  it("TEST-12-03-06: resume button appears only for failed runs", async () => {
    // First test: completed run should NOT show resume button
    mockedGetRunDetail.mockResolvedValue(sampleRun);
    mockedGetRunIdeas.mockResolvedValue({ ideas: sampleIdeas, total: 2 });

    renderRunDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("run-detail")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("resume-btn")).not.toBeInTheDocument();
  });

  it("TEST-12-03-06b: resume button appears for failed runs", async () => {
    const failedRun: PipelineRunDetail = {
      ...sampleRun,
      status: "failed",
      error_message: "Something went wrong",
      completed_at: null,
      stages_completed: ["literature_search"],
      current_stage: "gap_analysis",
    };
    mockedGetRunDetail.mockResolvedValue(failedRun);
    mockedGetRunIdeas.mockResolvedValue({ ideas: [], total: 0 });

    renderRunDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("resume-btn")).toBeInTheDocument();
    });

    expect(screen.getByTestId("resume-btn")).toHaveTextContent("Resume Pipeline");
  });

  // ── TEST-12-03-07: RunCard click navigates to /runs/:id ──

  it("TEST-12-03-07: RunCard click navigates to /runs/:id", async () => {
    // This tests the RunCard component's onClick behavior
    const { RunCard } = await import("@/components/pipeline/run-card");
    const mockNavigate = vi.fn();

    // Mock useNavigate
    vi.doMock("react-router-dom", () => ({
      ...vi.importActual("react-router-dom"),
      useNavigate: () => mockNavigate,
    }));

    const run = {
      id: 42,
      status: "completed" as const,
      domain: "NLP",
      current_stage: null,
      ideas_count: 5,
      created_at: "2025-01-01T00:00:00Z",
      completed_at: "2025-01-01T00:10:00Z",
      error_message: null,
    };

    render(
      <MemoryRouter>
        <RunCard run={run} onClick={() => mockNavigate("/runs/42")} />
      </MemoryRouter>,
    );

    const user = userEvent.setup();
    await user.click(screen.getByText(/Run #42/));
    expect(mockNavigate).toHaveBeenCalledWith("/runs/42");
  });

  // ── TEST-12-03-08: 404 run shows "Run not found" message ──

  it("TEST-12-03-08: 404 run shows run not found message", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    mockedGetRunDetail.mockRejectedValue(new Error("Not found"));

    renderRunDetail("99999");

    await waitFor(() => {
      expect(screen.getByTestId("run-not-found")).toBeInTheDocument();
    });

    expect(screen.getByText("Run not found")).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  // ── Quality Settings panel tests ──

  it("shows quality settings panel when config.quality_settings is present (orchestrator shape)", async () => {
    const runWithQuality: PipelineRunDetail = {
      ...sampleRun,
      config: {
        quality_settings: {
          proposal_depth: "detailed",
          novelty_depth: "thorough",
          idea_diversity: "exploratory",
          effective_min_words: { abstract: 225, proposed_method: 900 },
          effective_novelty_top_k: 50,
          effective_ideator_temperature: 1.1,
        },
      },
    };
    mockedGetRunDetail.mockResolvedValue(runWithQuality);
    mockedGetRunIdeas.mockResolvedValue({ ideas: sampleIdeas, total: 2 });

    renderRunDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("quality-settings")).toBeInTheDocument();
    });

    expect(screen.getByTestId("quality-proposal-depth")).toHaveTextContent("detailed");
    expect(screen.getByTestId("quality-novelty-depth")).toHaveTextContent("thorough");
    expect(screen.getByTestId("quality-idea-diversity")).toHaveTextContent("exploratory");
    expect(screen.getByTestId("quality-effective-topk")).toHaveTextContent("50");
    expect(screen.getByTestId("quality-effective-temp")).toHaveTextContent("1.10");
    expect(screen.getByTestId("quality-effective-minwords")).toHaveTextContent("900");
  });

  it("shows quality settings panel when config.quality is present (route shape)", async () => {
    const runWithQuality: PipelineRunDetail = {
      ...sampleRun,
      config: {
        quality: {
          proposal_depth: "detailed",
          novelty_depth: "thorough",
          idea_diversity: "exploratory",
          effective: {
            min_words: { abstract: 225, proposed_method: 900 },
            novelty_top_k: 50,
            ideator_temperature: 1.1,
          },
        },
      },
    };
    mockedGetRunDetail.mockResolvedValue(runWithQuality);
    mockedGetRunIdeas.mockResolvedValue({ ideas: sampleIdeas, total: 2 });

    renderRunDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("quality-settings")).toBeInTheDocument();
    });

    expect(screen.getByTestId("quality-proposal-depth")).toHaveTextContent("detailed");
    expect(screen.getByTestId("quality-novelty-depth")).toHaveTextContent("thorough");
    expect(screen.getByTestId("quality-idea-diversity")).toHaveTextContent("exploratory");
    expect(screen.getByTestId("quality-effective-topk")).toHaveTextContent("50");
    expect(screen.getByTestId("quality-effective-temp")).toHaveTextContent("1.10");
    expect(screen.getByTestId("quality-effective-minwords")).toHaveTextContent("900");
  });

  it("does not show quality settings panel when config.quality is absent", async () => {
    mockedGetRunDetail.mockResolvedValue(sampleRun);
    mockedGetRunIdeas.mockResolvedValue({ ideas: sampleIdeas, total: 2 });

    renderRunDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("run-detail")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("quality-settings")).not.toBeInTheDocument();
  });
});
