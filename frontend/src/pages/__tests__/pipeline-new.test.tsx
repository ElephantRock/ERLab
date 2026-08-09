import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import PipelineNew from "@/pages/pipeline-new";

// ── Mock child components (AR-03) ────────────────────────────────
vi.mock("@/components/pipeline/run-config-form", () => ({
  RunConfigForm: ({
    onSubmit,
    isLoading,
    onStrategyChange,
    onExperimentSpecChange,
  }: {
    onSubmit: (config: Record<string, unknown>) => void;
    isLoading: boolean;
    onStrategyChange?: (strategy: string) => void;
    onExperimentSpecChange?: (specId: string | null) => void;
  }) => (
    <div data-testid="run-config-form">
      <button data-testid="select-deep" onClick={() => onStrategyChange?.("deep_research")}>Deep</button>
      <button data-testid="select-registered" onClick={() => onExperimentSpecChange?.("phase5-pilot-v1")}>Registered</button>
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
  getEstimate: vi.fn().mockResolvedValue({
    strategy: "fast_scan",
    stages: 10,
    estimated_time_display: "~5 min",
    cost_display: "Free",
    local_cost_usd: 0,
    cloud_cost_usd: 0,
    breakdown: [],
  }),
}));

vi.mock("@/api/experiments", () => ({
  listExperimentSpecs: vi.fn().mockResolvedValue({
    compatible_strategies: ["academic_proposal", "deep_research"],
    specs: [
      {
        spec_id: "phase5-pilot-v1",
        description: "Iris pilot",
        research_question: "Does logistic regression classify Iris species?",
        dataset_name: "iris",
        analysis_method: "logistic_regression",
        primary_metric: "balanced_accuracy",
      },
    ],
  }),
}));

vi.mock("@/api/status", () => ({
  getSystemStatus: vi.fn().mockResolvedValue({
    app_name: "Elephant Rock Research",
    version: "0.1.0",
    config: {
      default_provider: "lmstudio",
      memory_enabled: true,
      governance_enabled: true,
    },
    defaults: {},
  }),
}));

import { triggerRun, cancelRun, getEstimate } from "@/api/pipeline";

const mockedTriggerRun = vi.mocked(triggerRun);
const mockedCancelRun = vi.mocked(cancelRun);
const mockedGetEstimate = vi.mocked(getEstimate);

function renderPipelineNew() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <PipelineNew />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("PipelineNew", () => {
  // ── TEST-11-01-06: Renders without crashing ─────────────────────
  it("TEST-11-01-06: renders without crashing", () => {
    renderPipelineNew();

    expect(screen.getByText("New Run")).toBeInTheDocument();
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

  it("updates the estimate/preview request when a registered experiment is selected", async () => {
    const user = userEvent.setup();
    mockedGetEstimate.mockImplementation(async (strategy: string, experimentSpecId?: string | null) => ({
      strategy,
      stages: experimentSpecId ? 2 : 1,
      estimated_cost_usd: 0,
      estimated_time_seconds: 60,
      estimated_time_display: "1 min",
      cost_display: "$0.00",
      local_cost_usd: 0,
      cloud_cost_usd: 0,
      breakdown: experimentSpecId
        ? [
            { stage: "literature_search", model: "local", label: "local", input_tokens: 0, output_tokens: 0, cost_usd: 0, time_seconds: 10 },
            { stage: "experiment_execution", model: "system", label: "system", input_tokens: 0, output_tokens: 0, cost_usd: 0, time_seconds: 50 },
          ]
        : [{ stage: "literature_search", model: "local", label: "local", input_tokens: 0, output_tokens: 0, cost_usd: 0, time_seconds: 10 }],
    }));

    renderPipelineNew();
    await user.click(screen.getByTestId("select-deep"));
    await user.click(screen.getByTestId("select-registered"));

    await waitFor(() => {
      expect(mockedGetEstimate).toHaveBeenCalledWith("deep_research", "phase5-pilot-v1");
      expect(screen.getByText("Experiment")).toBeInTheDocument();
      expect(screen.getByText("phase5-pilot-v1")).toBeInTheDocument();
    });
  });

  // ── TEST-11-01-08: Handles SSE connection error ─────────────────
  it("TEST-11-01-08: handles trigger error and displays message", async () => {
    const user = userEvent.setup();
    mockedTriggerRun.mockRejectedValue(new Error("Connection refused"));

    renderPipelineNew();

    const submitBtn = screen.getByTestId("submit-btn");
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("Failed to start pipeline")).toBeInTheDocument();
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
      expect(screen.getByTestId("live-badge")).toBeInTheDocument();
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
