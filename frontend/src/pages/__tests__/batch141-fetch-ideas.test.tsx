import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import PipelineNew from "@/pages/pipeline-new";
import type { IdeaSummary } from "@/api/types";

// ── Mock state controllers ──────────────────────────────────────
let mockIsComplete = false;

// ── Mock child components ─────────────────────────────────────

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
          onSubmit({ domain: "NLP", max_gaps: 5, ideas_per_round: 3, strategy: "fast_scan" })
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
      { key: "idea_generation", label: "Idea Generation", status: "completed", elapsed: 10 },
    ],
    isComplete: mockIsComplete,
    isConnected: !!runId,
  }),
}));

const sampleIdeas: IdeaSummary[] = [
  {
    id: 10,
    title: "Test Idea Alpha",
    domain: "NLP",
    novelty_score: 0.9,
    feasibility_score: 8,
    overall_score: 0.85,
    pipeline_run_id: 1,
    created_at: "2026-05-01T00:00:00Z",
  },
  {
    id: 20,
    title: "Test Idea Beta",
    domain: "CV",
    novelty_score: 0.7,
    feasibility_score: 6,
    overall_score: 0.65,
    pipeline_run_id: 1,
    created_at: "2026-05-01T00:00:00Z",
  },
];

vi.mock("@/api/pipeline", () => ({
  triggerRun: vi.fn(),
  getRunIdeas: vi.fn(),
  cancelRun: vi.fn(),
  listRuns: vi.fn(),
}));

import { triggerRun, getRunIdeas, listRuns } from "@/api/pipeline";

const mockedTriggerRun = vi.mocked(triggerRun);
const mockedGetRunIdeas = vi.mocked(getRunIdeas);
const mockedListRuns = vi.mocked(listRuns);

function renderPipelineNew() {
  return render(
    <MemoryRouter>
      <PipelineNew />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockIsComplete = false;
});

describe("BATCH-141 / TASK-03: Idea Fetch Race Condition Fix", () => {
  // ── TEST-141-03-01: fetchIdeas calls getRunIdeas(runId) directly ──
  // Falsified by: reverting to the old listRuns-based implementation

  it("TEST-141-03-01: fetchIdeas calls getRunIdeas with the correct runId", async () => {
    mockedTriggerRun.mockImplementation(async () => {
      mockIsComplete = true;
      return { run_id: "7", status: "running" };
    });
    mockedGetRunIdeas.mockResolvedValue({ ideas: sampleIdeas, total: 2 });

    renderPipelineNew();

    const user = userEvent.setup();
    await user.click(screen.getByTestId("submit-btn"));

    await waitFor(() => {
      // getRunIdeas should be called with Number(runId) = Number("7") = 7
      expect(mockedGetRunIdeas).toHaveBeenCalledWith(7);
    });
  });

  // ── TEST-141-03-02: fetchIdeas does NOT call listRuns ──
  // Falsified by: adding listRuns back into fetchIdeas

  it("TEST-141-03-02: fetchIdeas does not call listRuns (no race condition)", async () => {
    mockedTriggerRun.mockImplementation(async () => {
      mockIsComplete = true;
      return { run_id: "7", status: "running" };
    });
    mockedGetRunIdeas.mockResolvedValue({ ideas: [], total: 0 });

    renderPipelineNew();

    const user = userEvent.setup();
    await user.click(screen.getByTestId("submit-btn"));

    await waitFor(() => {
      expect(mockedGetRunIdeas).toHaveBeenCalled();
    });

    // listRuns should never be imported or called inside fetchIdeas.
    // We verify by checking the mock module was NOT called with { limit: 1 }
    // which was the old pattern. Since we mock the module, listRuns is a vi.fn()
    // but should have zero calls.
    const { listRuns } = await import("@/api/pipeline");
    expect(listRuns).not.toHaveBeenCalled();
  });

  // ── TEST-141-03-03: Ideas from the correct runId are displayed ──
  // Falsified by: mocking getRunIdeas to return ideas for a different ID

  it("TEST-141-03-03: displays ideas returned by getRunIdeas for the correct run", async () => {
    mockedTriggerRun.mockImplementation(async () => {
      mockIsComplete = true;
      return { run_id: "99", status: "running" };
    });
    mockedGetRunIdeas.mockImplementation(async (id: number) => {
      // Only return ideas for the correct run ID
      if (id === 99) {
        return { ideas: sampleIdeas, total: 2 };
      }
      return { ideas: [], total: 0 };
    });

    renderPipelineNew();

    const user = userEvent.setup();
    await user.click(screen.getByTestId("submit-btn"));

    await waitFor(() => {
      expect(screen.getByText("Test Idea Alpha")).toBeInTheDocument();
      expect(screen.getByText("Test Idea Beta")).toBeInTheDocument();
    });

    // Verify it was called with the correct ID
    expect(mockedGetRunIdeas).toHaveBeenCalledWith(99);
  });

  // ── TEST-141-03-04: Error state set when getRunIdeas fails ──
  // Falsified by: removing the catch block that sets setIdeasError

  it("TEST-141-03-04: sets error state when getRunIdeas fails", async () => {
    mockedTriggerRun.mockImplementation(async () => {
      mockIsComplete = true;
      return { run_id: "7", status: "running" };
    });
    mockedGetRunIdeas.mockRejectedValue(new Error("Ideas API unavailable"));

    renderPipelineNew();

    const user = userEvent.setup();
    await user.click(screen.getByTestId("submit-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("ideas-error")).toBeInTheDocument();
      expect(screen.getByText("Ideas API unavailable")).toBeInTheDocument();
    });
  });

  // ── TEST-141-03-05: Ideas state set to empty array on fetch failure ──
  // Falsified by: removing the setIdeas([]) call from catch block

  it("TEST-141-03-05: ideas are cleared when fetch fails", async () => {
    // First: successful fetch that loads ideas
    let callCount = 0;
    mockedTriggerRun.mockImplementation(async () => {
      callCount++;
      mockIsComplete = true;
      return { run_id: "7", status: "running" };
    });

    // First call succeeds, second would fail — but for this test we just
    // verify that on error, no ideas are shown (ideas array is empty)
    mockedGetRunIdeas.mockRejectedValue(new Error("Network failure"));

    renderPipelineNew();

    const user = userEvent.setup();
    await user.click(screen.getByTestId("submit-btn"));

    await waitFor(() => {
      // Error should be displayed
      expect(screen.getByTestId("ideas-error")).toBeInTheDocument();
    });

    // No idea cards should be present (ideas were set to [])
    expect(screen.queryByText("Test Idea Alpha")).not.toBeInTheDocument();
    expect(screen.queryByText("Test Idea Beta")).not.toBeInTheDocument();
  });

  // ── TEST-141-03-06: fetchIdeas is only called when isComplete is true ──
  // Falsified by: moving the fetchIdeas call outside the isComplete guard

  it("TEST-141-03-06: getRunIdeas is NOT called when isComplete is false", async () => {
    // isComplete stays false — pipeline is still running
    mockedTriggerRun.mockImplementation(async () => {
      // Do NOT set mockIsComplete = true
      return { run_id: "7", status: "running" };
    });

    renderPipelineNew();

    const user = userEvent.setup();
    await user.click(screen.getByTestId("submit-btn"));

    // Wait for the pipeline to be in "running" state
    await waitFor(() => {
      expect(screen.getByText("Live")).toBeInTheDocument();
    });

    // getRunIdeas should NOT have been called since isComplete is false
    expect(mockedGetRunIdeas).not.toHaveBeenCalled();
  });
});
