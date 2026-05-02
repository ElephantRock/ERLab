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
}));

import { triggerRun } from "@/api/pipeline";

const mockedTriggerRun = vi.mocked(triggerRun);

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
    // Autonomous tab content is hidden by Radix until clicked — only tab trigger is visible
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
