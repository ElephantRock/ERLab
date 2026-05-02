/**
 * Tests for BATCH-26/TASK-02: Autonomous Dashboard Components
 *
 * TEST-26-02-01: API client calls correct endpoints
 * TEST-26-02-02: CycleProgress renders cycle info
 * TEST-26-02-03: ConsciousnessState shows current state badge
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { getAutonomousHistory, stopAutonomousCycle } from "@/api/autonomous";
import { apiFetch } from "@/api/client";
import { CycleProgress } from "@/components/autonomous/cycle-progress";
import { ConsciousnessStateBadge } from "@/components/autonomous/consciousness-state";
import type { AutonomousCycleHistoryEntry } from "@/api/autonomous";

// ── Mock apiFetch ───────────────────────────────────────────────

vi.mock("@/api/client", () => ({
  apiFetch: vi.fn(),
}));

const mockApiFetch = vi.mocked(apiFetch);

// ── TEST-26-02-01: API client calls correct endpoints ───────────

describe("BATCH-26/TASK-02: Autonomous API Client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("TEST-26-02-01: API client calls correct endpoints", async () => {
    // Test getAutonomousHistory
    const mockHistory = {
      cycles: [
        {
          cycle_id: "auto_20260502_143000",
          domain: "AI/NLP",
          runs: 3,
          status: "completed",
        },
      ],
    };
    mockApiFetch.mockResolvedValueOnce(mockHistory);

    const result = await getAutonomousHistory();

    expect(mockApiFetch).toHaveBeenCalledWith("/pipeline/autonomous/history");
    expect(result.cycles).toHaveLength(1);
    expect(result.cycles[0].cycle_id).toBe("auto_20260502_143000");
    expect(result.cycles[0].status).toBe("completed");

    // Test stopAutonomousCycle
    mockApiFetch.mockResolvedValueOnce({ status: "stopped", cycle_id: "auto_test" });

    await stopAutonomousCycle("auto_test");

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/pipeline/autonomous/stop?cycle_id=auto_test",
      { method: "POST" },
    );
  });
});

// ── TEST-26-02-02: CycleProgress renders cycle info ─────────────

describe("CycleProgress", () => {
  const mockCycle: AutonomousCycleHistoryEntry = {
    cycle_id: "auto_20260502_143000",
    domain: "AI/NLP",
    runs: 3,
    status: "running",
  };

  it("TEST-26-02-02: CycleProgress renders cycle info", () => {
    render(<CycleProgress cycle={mockCycle} />);

    expect(screen.getByTestId("cycle-progress-auto_20260502_143000")).toBeInTheDocument();
    expect(screen.getByText("auto_20260502_143000")).toBeInTheDocument();
    expect(screen.getByTestId("cycle-domain-auto_20260502_143000")).toHaveTextContent("AI/NLP");
    expect(screen.getByTestId("cycle-runs-auto_20260502_143000")).toHaveTextContent("3 runs");
    expect(screen.getByText("running")).toBeInTheDocument();
  });

  it("shows stop button when running and onStop provided", () => {
    const onStop = vi.fn();
    render(<CycleProgress cycle={mockCycle} onStop={onStop} />);

    expect(screen.getByTestId("cycle-stop-auto_20260502_143000")).toBeInTheDocument();
  });

  it("hides stop button when cycle is completed", () => {
    const completedCycle = { ...mockCycle, status: "completed" as const };
    const onStop = vi.fn();
    render(<CycleProgress cycle={completedCycle} onStop={onStop} />);

    expect(screen.queryByTestId("cycle-stop-auto_20260502_143000")).not.toBeInTheDocument();
  });
});

// ── TEST-26-02-03: ConsciousnessState shows current state badge ──

describe("ConsciousnessStateBadge", () => {
  it("TEST-26-02-03: ConsciousnessState shows current state badge", () => {
    render(<ConsciousnessStateBadge state="exploring" />);

    expect(screen.getByTestId("consciousness-state")).toBeInTheDocument();
    expect(screen.getByTestId("consciousness-badge")).toHaveTextContent("Exploring");
  });

  it("shows seconds when provided", () => {
    render(<ConsciousnessStateBadge state="generating" secondsInState={42.7} />);

    expect(screen.getByTestId("consciousness-badge")).toHaveTextContent("Generating");
    expect(screen.getByTestId("consciousness-seconds")).toHaveTextContent("43s");
  });

  it("renders idle state by default", () => {
    render(<ConsciousnessStateBadge state="idle" />);

    expect(screen.getByTestId("consciousness-badge")).toHaveTextContent("Idle");
  });
});
