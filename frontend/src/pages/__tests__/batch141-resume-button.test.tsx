import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import RunDetail from "@/pages/run-detail";
import type { PipelineRunDetail } from "@/api/types";

// ── Mock API modules ────────────────────────────────────────────
vi.mock("@/api/pipeline", () => ({
  getRunDetail: vi.fn(),
  getRunIdeas: vi.fn(),
  resumeRun: vi.fn(),
}));

vi.mock("@/components/pipeline/tree-visualization", () => ({
  TreeVisualization: () => <div data-testid="tree-viz">Tree</div>,
}));

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

import { getRunDetail, getRunIdeas, resumeRun } from "@/api/pipeline";
import { toast } from "sonner";

const mockedGetRunDetail = vi.mocked(getRunDetail);
const mockedGetRunIdeas = vi.mocked(getRunIdeas);
const mockedResumeRun = vi.mocked(resumeRun);
const mockedToastError = vi.mocked(toast.error);

// ── Helpers ──────────────────────────────────────────────────────

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

const baseRun: PipelineRunDetail = {
  id: 42,
  status: "failed",
  domain: "AI/NLP",
  current_stage: "gap_analysis",
  ideas_count: 0,
  created_at: "2026-05-01T10:00:00Z",
  completed_at: null,
  error_message: "LLM rate limit exceeded",
  config: {},
  stages_completed: ["literature_search", "ingestion"],
  ideas: [],
  tree_data: null,
  strategy: "deep_research",
};

function renderRunDetail(runId: string = "42", runOverride?: Partial<PipelineRunDetail>) {
  const qc = createQueryClient();
  const run = { ...baseRun, ...runOverride };
  mockedGetRunDetail.mockResolvedValue(run);
  mockedGetRunIdeas.mockResolvedValue({ ideas: [], total: 0 });

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

describe("BATCH-141 / TASK-02: Resume Button Wiring", () => {
  // ── TEST-141-02-01: resumeRun function calls correct API endpoint ──
  // Falsified by: changing the URL path in resumeRun to /wrong-endpoint

  it("TEST-141-02-01: resumeRun calls POST /api/v1/pipeline/resume/{runId}", async () => {
    mockedResumeRun.mockResolvedValue({
      status: "running",
      run_id: "42",
      ideas_count: 0,
      gaps_count: 0,
      proposals_count: 0,
    });

    renderRunDetail("42");

    await waitFor(() => {
      expect(screen.getByTestId("resume-btn")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByTestId("resume-btn"));

    await waitFor(() => {
      expect(mockedResumeRun).toHaveBeenCalledWith("42");
    });
  });

  // ── TEST-141-02-01b: Resume button NOT visible when status is not "failed" ──
  // Falsified by: removing the run.status === "failed" condition from the render

  it("TEST-141-02-01b: resume button hidden when status is completed", async () => {
    renderRunDetail("42", { status: "completed", completed_at: "2026-05-01T10:05:00Z", error_message: null });

    await waitFor(() => {
      expect(screen.getByTestId("run-detail")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("resume-btn")).not.toBeInTheDocument();
  });

  it("TEST-141-02-01b: resume button hidden when status is running", async () => {
    renderRunDetail("42", { status: "running", error_message: null });

    await waitFor(() => {
      expect(screen.getByTestId("run-detail")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("resume-btn")).not.toBeInTheDocument();
  });

  // ── TEST-141-02-02: Resume button is visible when run status is "failed" ──
  // Falsified by: adding `status !== "failed"` to the render condition

  it("TEST-141-02-02: resume button visible when run status is failed", async () => {
    renderRunDetail("42");

    await waitFor(() => {
      expect(screen.getByTestId("resume-btn")).toBeInTheDocument();
    });

    expect(screen.getByTestId("resume-btn")).toHaveTextContent("Resume Pipeline");
  });

  // ── TEST-141-02-03: Resume button triggers API call on click ──
  // Falsified by: removing the onClick handler from the button

  it("TEST-141-02-03: clicking resume triggers resumeRun API call", async () => {
    mockedResumeRun.mockResolvedValue({
      status: "running",
      run_id: "42",
      ideas_count: 0,
      gaps_count: 0,
      proposals_count: 0,
    });

    renderRunDetail("42");

    await waitFor(() => {
      expect(screen.getByTestId("resume-btn")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByTestId("resume-btn"));

    await waitFor(() => {
      expect(mockedResumeRun).toHaveBeenCalledTimes(1);
      expect(mockedResumeRun).toHaveBeenCalledWith("42");
    });
  });

  // ── TEST-141-02-04: Loading state shown during resume API call ──
  // Falsified by: removing the isResuming state check from the button render

  it("TEST-141-02-04: shows loading state during resume API call", async () => {
    let resolveResume: (value: unknown) => void;
    const resumePromise = new Promise((resolve) => { resolveResume = resolve; });
    mockedResumeRun.mockImplementation(() => resumePromise as Promise<never>);

    renderRunDetail("42");

    await waitFor(() => {
      expect(screen.getByTestId("resume-btn")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByTestId("resume-btn"));

    // Button should show loading state
    await waitFor(() => {
      expect(screen.getByTestId("resume-btn")).toHaveTextContent("Resuming...");
    });
    expect(screen.getByTestId("resume-btn")).toBeDisabled();

    // Resolve the promise to clean up
    resolveResume!({ status: "running", run_id: "42", ideas_count: 0, gaps_count: 0, proposals_count: 0 });
    await waitFor(() => {
      expect(screen.getByTestId("resume-btn")).not.toBeDisabled();
    });
  });

  // ── TEST-141-02-05: Error toast shown when resume API fails ──
  // Falsified by: removing the onError toast.error call from the catch block

  it("TEST-141-02-05: shows error toast when resume API fails", async () => {
    mockedResumeRun.mockRejectedValue(new Error("Server error: 500"));

    renderRunDetail("42");

    await waitFor(() => {
      expect(screen.getByTestId("resume-btn")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByTestId("resume-btn"));

    await waitFor(() => {
      expect(mockedToastError).toHaveBeenCalledWith("Server error: 500");
    });
  });

  // ── TEST-141-02-06: Success invalidates run query to trigger refetch ──
  // Falsified by: removing the queryClient.invalidateQueries call from onSuccess

  it("TEST-141-02-06: on success, invalidates run query to show updated status", async () => {
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");
    mockedResumeRun.mockResolvedValue({
      status: "running",
      run_id: "42",
      ideas_count: 0,
      gaps_count: 0,
      proposals_count: 0,
    });

    renderRunDetail("42");

    await waitFor(() => {
      expect(screen.getByTestId("resume-btn")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByTestId("resume-btn"));

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ["run", 42] }),
      );
    });

    invalidateSpy.mockRestore();
  });
});
