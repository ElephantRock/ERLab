import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import PipelineNew from "@/pages/pipeline-new";

// ── Mock child components (AR-03) ────────────────────────────────
vi.mock("@/components/pipeline/run-config-form", () => ({
  RunConfigForm: ({
    onSubmit,
    isLoading,
  }: {
    onSubmit: (config: Record<string, unknown>) => void;
    isLoading: boolean;
  }) => (
    <div data-testid="run-config-form">
      <button
        data-testid="submit-btn"
        disabled={isLoading}
        onClick={() =>
          onSubmit({ domain: "NLP", max_gaps: 5, ideas_per_round: 3 })
        }
      >
        {isLoading ? "Starting…" : "Start Run"}
      </button>
    </div>
  ),
}));

vi.mock("@/components/pipeline/autonomous-form", () => ({
  AutonomousForm: ({ onCycleStarted }: { onCycleStarted: (id: string) => void }) => (
    <button data-testid="autonomous-btn" onClick={() => onCycleStarted("cycle-1")}>
      Start Autonomous
    </button>
  ),
}));

vi.mock("@/components/pipeline/stage-progress", () => ({
  StageProgress: ({ stages }: { stages: unknown[] }) => (
    <div data-testid="stage-progress">Stages: {stages.length}</div>
  ),
}));

vi.mock("@/hooks/usePipelineProgress", () => ({
  usePipelineProgress: (runId: string | null) => ({
    stages: [
      { key: "literature_search", label: "Literature Search", status: "completed", elapsed: 5 },
      { key: "ingestion", label: "PDF Ingestion", status: "running", elapsed: 3 },
    ],
    isComplete: false,
    isConnected: !!runId,
  }),
}));

vi.mock("@/api/pipeline", () => ({
  triggerRun: vi.fn(),
  cancelRun: vi.fn(),
  getRunIdeas: vi.fn(),
  listRuns: vi.fn(),
}));

import { triggerRun, cancelRun } from "@/api/pipeline";

const mockedTriggerRun = vi.mocked(triggerRun);
const mockedCancelRun = vi.mocked(cancelRun);

function renderPipelineNew() {
  return render(
    <MemoryRouter>
      <PipelineNew />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("PipelineNew", () => {
  // ── TEST-11-01-06: Renders without crashing ─────────────────────
  it("TEST-11-01-06: renders without crashing", () => {
    renderPipelineNew();

    expect(screen.getByText("Pipeline")).toBeInTheDocument();
    expect(
      screen.getByText("Configure and launch a research pipeline."),
    ).toBeInTheDocument();
  });

  // ── TEST-11-01-07: Shows run config form ────────────────────────
  it("TEST-11-01-07: shows run config form with tabs", () => {
    renderPipelineNew();

    expect(screen.getByTestId("run-config-form")).toBeInTheDocument();
    expect(screen.getByText("Single Run")).toBeInTheDocument();
    expect(screen.getByText("Autonomous Cycle")).toBeInTheDocument();
  });

  // ── TEST-11-01-08: Handles SSE connection error ─────────────────
  it("TEST-11-01-08: handles trigger error and displays message", async () => {
    const user = userEvent.setup();
    mockedTriggerRun.mockRejectedValue(new Error("Connection refused"));

    renderPipelineNew();

    const submitBtn = screen.getByTestId("submit-btn");
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("Connection refused")).toBeInTheDocument();
    });
  });
});

// ── BATCH-15 / TASK-01: Cancel Pipeline UI ──────────────────────
describe("PipelineNew – Cancel Run (BATCH-15)", () => {
  async function startRunningPipeline() {
    const user = userEvent.setup();
    mockedTriggerRun.mockResolvedValue({
      run_id: "run_20260502_test",
      status: "running",
    });

    renderPipelineNew();

    const submitBtn = screen.getByTestId("submit-btn");
    await user.click(submitBtn);

    // Wait for the pipeline to be in "running" state
    await waitFor(() => {
      expect(screen.getByText("Live")).toBeInTheDocument();
    });
  }

  // ── TEST-15-01-01: Cancel button renders during pipeline execution ──
  it("TEST-15-01-01: cancel button renders during pipeline execution", async () => {
    await startRunningPipeline();

    expect(screen.getByTestId("cancel-run-btn")).toBeInTheDocument();
    expect(screen.getByTestId("cancel-run-btn")).toHaveTextContent("Cancel Run");
  });

  // ── TEST-15-01-02: Cancel click shows confirmation dialog ──────
  it("TEST-15-01-02: cancel click shows confirmation dialog", async () => {
    await startRunningPipeline();

    const user = userEvent.setup();
    const cancelBtn = screen.getByTestId("cancel-run-btn");
    await user.click(cancelBtn);

    expect(screen.getByTestId("cancel-confirm-dialog")).toBeInTheDocument();
    expect(screen.getByText("Cancel Pipeline Run?")).toBeInTheDocument();
    expect(screen.getByTestId("cancel-confirm-btn")).toBeInTheDocument();
    expect(screen.getByTestId("cancel-dismiss-btn")).toBeInTheDocument();
  });

  // ── TEST-15-01-03: Cancel confirm calls cancelRun() ────────────
  it("TEST-15-01-03: cancel confirm calls cancelRun()", async () => {
    mockedCancelRun.mockResolvedValue({
      status: "cancelled",
      run_id: "run_20260502_test",
    });

    await startRunningPipeline();

    const user = userEvent.setup();
    // Open confirmation dialog
    await user.click(screen.getByTestId("cancel-run-btn"));
    // Confirm cancellation
    await user.click(screen.getByTestId("cancel-confirm-btn"));

    await waitFor(() => {
      expect(mockedCancelRun).toHaveBeenCalledWith("run_20260502_test");
    });
  });

  // ── TEST-15-01-04: Cancelled state shows "Cancelled" badge ─────
  it("TEST-15-01-04: cancelled state shows Cancelled badge", async () => {
    mockedCancelRun.mockResolvedValue({
      status: "cancelled",
      run_id: "run_20260502_test",
    });

    await startRunningPipeline();

    const user = userEvent.setup();
    await user.click(screen.getByTestId("cancel-run-btn"));
    await user.click(screen.getByTestId("cancel-confirm-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("cancelled-badge")).toBeInTheDocument();
      expect(screen.getByTestId("cancelled-badge")).toHaveTextContent("Cancelled");
    });
  });

  // ── TEST-15-01-05: Cancelled state shows partial results ───────
  it("TEST-15-01-05: cancelled state shows partial results if available", async () => {
    mockedCancelRun.mockResolvedValue({
      status: "cancelled",
      run_id: "run_20260502_test",
    });

    await startRunningPipeline();

    const user = userEvent.setup();
    await user.click(screen.getByTestId("cancel-run-btn"));
    await user.click(screen.getByTestId("cancel-confirm-btn"));

    await waitFor(() => {
      const partial = screen.getByTestId("cancelled-partial-results");
      expect(partial).toBeInTheDocument();
      // The mock has 1 completed stage ("literature_search") and 2 total stages
      expect(partial.textContent).toContain("1 of 2 stage completed before cancellation");
    });
  });
});
