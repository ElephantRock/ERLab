import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import PipelineNew from "@/pages/pipeline-new";
import type { IdeaSummary } from "@/api/types";

// ── Mock child components ─────────────────────────────────────

let mockIsComplete = false;
let mockRunId: string | null = null;

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
      { key: "idea_generation", label: "Idea Generation", status: "completed", elapsed: 10 },
    ],
    isComplete: mockIsComplete,
    isConnected: !!runId,
  }),
}));

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

vi.mock("@/api/pipeline", () => ({
  triggerRun: vi.fn(),
  getRunIdeas: vi.fn(),
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
  mockRunId = null;
});

describe("PipelineNew - Results Display (BATCH-12/TASK-02)", () => {
  // ── TEST-12-02-01: Results section renders after pipeline completion ──

  it("TEST-12-02-01: renders results section after pipeline completion", async () => {
    mockedTriggerRun.mockImplementation(async () => {
      mockIsComplete = true;
      return { run_id: "run_1", status: "running" };
    });
    mockedListRuns.mockResolvedValue({ runs: [{ id: 1, ideas_count: 2 }], total: 1 } as never);
    mockedGetRunIdeas.mockResolvedValue({ ideas: sampleIdeas, total: 2 });

    renderPipelineNew();

    // Initially no results section
    expect(screen.queryByTestId("pipeline-results")).not.toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByTestId("submit-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("pipeline-results")).toBeInTheDocument();
    });
  });

  // ── TEST-12-02-02: Shows "Pipeline Complete" banner with summary stats ──

  it("TEST-12-02-02: shows Pipeline Complete banner with idea count", async () => {
    mockedTriggerRun.mockImplementation(async () => {
      mockIsComplete = true;
      return { run_id: "run_1", status: "running" };
    });
    mockedListRuns.mockResolvedValue({ runs: [{ id: 1, ideas_count: 2 }], total: 1 } as never);
    mockedGetRunIdeas.mockResolvedValue({ ideas: sampleIdeas, total: 2 });

    renderPipelineNew();

    const user = userEvent.setup();
    await user.click(screen.getByTestId("submit-btn"));

    await waitFor(() => {
      expect(screen.getByText("Pipeline Complete")).toBeInTheDocument();
      expect(screen.getByText("2 ideas generated")).toBeInTheDocument();
    });
  });

  // ── TEST-12-02-03: Generated ideas appear as idea cards ──

  it("TEST-12-02-03: shows generated ideas as clickable cards", async () => {
    mockedTriggerRun.mockImplementation(async () => {
      mockIsComplete = true;
      return { run_id: "run_1", status: "running" };
    });
    mockedListRuns.mockResolvedValue({ runs: [{ id: 1, ideas_count: 2 }], total: 1 } as never);
    mockedGetRunIdeas.mockResolvedValue({ ideas: sampleIdeas, total: 2 });

    renderPipelineNew();

    const user = userEvent.setup();
    await user.click(screen.getByTestId("submit-btn"));

    await waitFor(() => {
      expect(screen.getByText("Cross-lingual Transfer")).toBeInTheDocument();
      expect(screen.getByText("Few-shot Prompting")).toBeInTheDocument();
    });
  });

  // ── TEST-12-02-04: "View All Ideas" button links to /ideas ──

  it("TEST-12-02-04: View All Ideas button is present", async () => {
    mockedTriggerRun.mockImplementation(async () => {
      mockIsComplete = true;
      return { run_id: "run_1", status: "running" };
    });
    mockedListRuns.mockResolvedValue({ runs: [{ id: 1, ideas_count: 1 }], total: 1 } as never);
    mockedGetRunIdeas.mockResolvedValue({ ideas: sampleIdeas, total: 2 });

    renderPipelineNew();

    const user = userEvent.setup();
    await user.click(screen.getByTestId("submit-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("view-all-ideas")).toBeInTheDocument();
      expect(screen.getByTestId("view-all-ideas")).toHaveTextContent("View All Ideas");
    });
  });

  // ── TEST-12-02-05: "Run Another" button resets form state ──

  it("TEST-12-02-05: Run Another button resets form state", async () => {
    let callCount = 0;
    mockedTriggerRun.mockImplementation(async () => {
      callCount++;
      if (callCount === 1) {
        mockIsComplete = true;
      }
      return { run_id: "run_1", status: "running" };
    });
    mockedListRuns.mockResolvedValue({ runs: [{ id: 1, ideas_count: 1 }], total: 1 } as never);
    mockedGetRunIdeas.mockResolvedValue({ ideas: sampleIdeas, total: 2 });

    renderPipelineNew();

    const user = userEvent.setup();
    await user.click(screen.getByTestId("submit-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("run-another")).toBeInTheDocument();
    });

    // Clicking "Run Another" resets, which sets isComplete back to false
    mockIsComplete = false;
    await user.click(screen.getByTestId("run-another"));

    // After reset, the config form should be visible again and results gone
    await waitFor(() => {
      expect(screen.getByTestId("run-config-form")).toBeInTheDocument();
      expect(screen.queryByTestId("pipeline-results")).not.toBeInTheDocument();
    });
  });

  // ── TEST-12-02-06: Ideas fetch error shows error message ──

  it("TEST-12-02-06: shows error message when ideas fetch fails", async () => {
    mockedTriggerRun.mockImplementation(async () => {
      mockIsComplete = true;
      return { run_id: "run_1", status: "running" };
    });
    mockedListRuns.mockRejectedValue(new Error("Network error"));
    mockedGetRunIdeas.mockRejectedValue(new Error("Network error"));

    renderPipelineNew();

    const user = userEvent.setup();
    await user.click(screen.getByTestId("submit-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("ideas-error")).toBeInTheDocument();
      expect(screen.getByText("Failed to load results")).toBeInTheDocument();
    });
  });
});
