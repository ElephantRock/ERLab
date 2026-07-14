/**
 * Tests for BATCH-26/TASK-03: Autonomous Dashboard Page
 *
 * TEST-26-03-01: Page renders with cycle controls
 * TEST-26-03-02: Start cycle form visible
 * TEST-26-03-03: Stop button requires confirmation
 * TEST-26-03-04: History list renders
 * TEST-26-03-05: Consciousness state displayed
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AutonomousPage from "@/pages/autonomous";

// ── Mock the autonomous API ────────────────────────────────────

const mockHistory = {
  cycles: [
    {
      cycle_id: "auto_20260502_143000",
      domain: "AI/NLP",
      runs: 3,
      status: "completed",
    },
    {
      cycle_id: "auto_20260502_150000",
      domain: "Physics",
      runs: 1,
      status: "running",
    },
  ],
};

vi.mock("@/api/autonomous", () => ({
  getAutonomousHistory: vi.fn(),
  stopAutonomousCycle: vi.fn(),
  triggerAutonomous: vi.fn(),
  getConsciousnessState: vi.fn(),
  getSchedulerStatus: vi.fn(),
  getEvolutionStatus: vi.fn(),
  startScheduler: vi.fn(),
  stopScheduler: vi.fn(),
}));

import {
  getAutonomousHistory,
  stopAutonomousCycle,
  triggerAutonomous,
  getSchedulerStatus,
  getEvolutionStatus,
  getConsciousnessState,
} from "@/api/autonomous";

function setupMocks() {
  vi.mocked(getAutonomousHistory).mockResolvedValue(mockHistory);
  vi.mocked(stopAutonomousCycle).mockResolvedValue({
    status: "stopped",
    cycle_id: "auto_20260502_150000",
  });
  vi.mocked(triggerAutonomous).mockResolvedValue({
    cycle_id: "auto_20260502_160000",
    status: "running",
    domain: "AI/NLP",
    max_runs: 3,
  });
  // The migrated page now calls these on mount via useQuery. Provide
  // honest defaults so the inline status cards render without errors.
  vi.mocked(getSchedulerStatus).mockResolvedValue({ status: "stopped" });
  vi.mocked(getEvolutionStatus).mockResolvedValue({
    enabled: false,
    overlays_generated: 0,
    recent_outcomes: [],
  });
  vi.mocked(getConsciousnessState).mockResolvedValue({ state: "idle", seconds_in_state: 0, next_action: "" });
}

// ── Helper ──────────────────────────────────────────────────────
// Autonomous page now uses useResource/useQuery (react-query backed),
// so the harness must provide a QueryClientProvider.
function renderAutonomousPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/autonomous"]}>
        <Routes>
          <Route path="/autonomous" element={<AutonomousPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("BATCH-26/TASK-03: Autonomous Dashboard Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── TEST-26-03-01: Page renders with cycle controls ────────
  it("TEST-26-03-01: Page renders with cycle controls", async () => {
    setupMocks();
    renderAutonomousPage();

    // Wait for the ready state — autonomous-page exists during loading too
    // (DataView renders inside it), so wait for the start form which is
    // always present once the page shell renders.
    await waitFor(() => {
      expect(screen.getByTestId("autonomous-start-form")).toBeInTheDocument();
    });

    expect(screen.getByText("Autonomous Cycles")).toBeInTheDocument();
    expect(screen.getByText("Monitor and control autonomous research cycles.")).toBeInTheDocument();
  });

  // ── TEST-26-03-02: Start cycle form visible ────────────────
  it("TEST-26-03-02: Start cycle form visible", async () => {
    setupMocks();
    renderAutonomousPage();

    await waitFor(() => {
      expect(screen.getByTestId("autonomous-start-form")).toBeInTheDocument();
    });

    expect(screen.getByTestId("domain-input")).toBeInTheDocument();
    expect(screen.getByTestId("max-runs-input")).toBeInTheDocument();
    expect(screen.getByTestId("start-cycle-btn")).toBeInTheDocument();
    expect(screen.getByTestId("domain-label")).toHaveTextContent("Domain");
  });

  // ── TEST-26-03-03: Stop button requires confirmation ───────
  it("TEST-26-03-03: Stop button requires confirmation", async () => {
    setupMocks();
    renderAutonomousPage();

    // Wait for history to load (the stop button is in a cycle card)
    await waitFor(() => {
      expect(screen.getByTestId("autonomous-history-list")).toBeInTheDocument();
    });

    // Find the stop button on the running cycle
    const stopBtn = screen.getByTestId("cycle-stop-auto_20260502_150000");
    expect(stopBtn).toBeInTheDocument();

    // Click stop — should show confirmation dialog (HB-01)
    await userEvent.click(stopBtn);

    expect(screen.getByTestId("stop-confirm-dialog")).toBeInTheDocument();
    expect(screen.getByTestId("stop-confirm-btn")).toBeInTheDocument();
    expect(screen.getByTestId("stop-cancel-btn")).toBeInTheDocument();

    // Cancel should dismiss
    await userEvent.click(screen.getByTestId("stop-cancel-btn"));
    expect(screen.queryByTestId("stop-confirm-dialog")).not.toBeInTheDocument();
  });

  // ── TEST-26-03-04: History list renders ────────────────────
  it("TEST-26-03-04: History list renders", async () => {
    setupMocks();
    renderAutonomousPage();

    await waitFor(() => {
      expect(screen.getByTestId("autonomous-history-list")).toBeInTheDocument();
    });

    expect(screen.getByTestId("history-heading")).toHaveTextContent("Cycle History");
    expect(screen.getByTestId("cycle-progress-auto_20260502_143000")).toBeInTheDocument();
    expect(screen.getByTestId("cycle-progress-auto_20260502_150000")).toBeInTheDocument();
  });

  // ── TEST-26-03-05: Consciousness state displayed ───────────
  it("TEST-26-03-05: Consciousness state displayed", async () => {
    setupMocks();
    renderAutonomousPage();

    await waitFor(() => {
      expect(screen.getByTestId("autonomous-start-form")).toBeInTheDocument();
    });

    expect(screen.getByTestId("consciousness-display")).toBeInTheDocument();
    expect(screen.getByTestId("consciousness-badge")).toHaveTextContent("Idle");
  });
});
