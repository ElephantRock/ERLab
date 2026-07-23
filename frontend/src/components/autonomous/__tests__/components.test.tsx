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
import { apiFetchJson } from "@/api/client";
import { CycleProgress } from "@/components/autonomous/cycle-progress";
// F1.1 H2: ConsciousnessStateBadge import removed — the component was
// deleted (it rendered a badge backed by a non-existent backend endpoint).
// The ConsciousnessStateBadge describe block below was also removed.
import type { AutonomousCycleHistoryEntry } from "@/api/autonomous";

// ── Mock apiFetchUnchecked + apiFetchJson ───────────────────────────────
// F1.3a: getAutonomousHistory now routes through callContract → apiFetchJson;
// stopAutonomousCycle remains on apiFetchUnchecked. Provide both.

vi.mock("@/api/client", () => ({
  apiFetchJson: vi.fn(),
}));

const mockApiFetchJson = vi.mocked(apiFetchJson);

// ── TEST-26-02-01: API client calls correct endpoints ───────────

describe("BATCH-26/TASK-02: Autonomous API Client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("TEST-26-02-01: API client calls correct endpoints", async () => {
    // Test getAutonomousHistory (F1.3a: migrated → apiFetchJson)
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
    mockApiFetchJson.mockResolvedValueOnce(mockHistory);

    const result = await getAutonomousHistory();

    expect(mockApiFetchJson).toHaveBeenCalled();
    expect(result.cycles).toHaveLength(1);
    expect(result.cycles[0].cycle_id).toBe("auto_20260502_143000");
    expect(result.cycles[0].status).toBe("completed");

    // Test stopAutonomousCycle (F1.7a: migrated → callContract → apiFetchJson)
    mockApiFetchJson.mockResolvedValueOnce({ status: "stopped", cycle_id: "auto_test" });

    await stopAutonomousCycle("auto_test");

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      expect.stringContaining("/pipeline/autonomous/stop"),
      expect.objectContaining({ method: "POST" }),
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

// F1.1 H2: ConsciousnessStateBadge describe block removed — the component
// was deleted (backed by a non-existent endpoint /pipeline/autonomous/consciousness).
