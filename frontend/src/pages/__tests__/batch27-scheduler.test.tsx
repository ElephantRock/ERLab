/**
 * Tests for BATCH-27/TASK-02: Self-Improvement Settings + Scheduler Controls
 *
 * TEST-27-02-01: Settings shows self-improve section (read-only)
 * TEST-27-02-02: Autonomous page shows scheduler start/stop
 * TEST-27-02-03: Evolution status displayed
 * TEST-27-02-04: Scheduler start calls API
 * TEST-27-02-05: Scheduler stop calls API
 * TEST-27-02-06: Scheduler status displayed
 * TEST-27-02-07: No edit controls for evolution params (HB-01)
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SettingsProvider } from "@/contexts/settings-context";
import { AuthProvider } from "@/contexts/auth-context";
import Settings from "@/pages/settings";
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
  ],
};

const mockEvolutionStatus = {
  enabled: true,
  overlays_generated: 5,
  recent_outcomes: [
    { stage_name: "idea_generation", score: 0.8, run_id: "run_1" },
    { stage_name: "evaluation", score: 0.65, run_id: "run_2" },
  ],
};

const mockSchedulerStatus = {
  status: "stopped",
};

vi.mock("@/api/autonomous", () => ({
  getAutonomousHistory: vi.fn(),
  stopAutonomousCycle: vi.fn(),
  triggerAutonomous: vi.fn(),
  getConsciousnessState: vi.fn(),
  getEvolutionStatus: vi.fn(),
  startScheduler: vi.fn(),
  stopScheduler: vi.fn(),
  getSchedulerStatus: vi.fn(),
}));

import {
  getAutonomousHistory,
  stopAutonomousCycle,
  triggerAutonomous,
  getEvolutionStatus,
  getConsciousnessState,
  startScheduler,
  stopScheduler,
  getSchedulerStatus,
} from "@/api/autonomous";

// ── Mock client for detailed status ────────────────────────────

vi.mock("@/api/client", () => ({
  testConnection: vi.fn().mockResolvedValue({ ok: true, version: "0.1.0" }),
  getDetailedStatus: vi.fn().mockResolvedValue({
    version: "0.1.0",
    provider: "openai",
    db_status: "ok",
  }),
  apiFetchUnchecked: vi.fn(),
  ApiError: class extends Error {},
  sseUrl: vi.fn(),
  getApiUrl: () => "",
  getApiKey: () => "",
  buildUrl: (p: string) => p,
  buildAuthHeaders: () => ({}),
}));

vi.mock("@/api/auth", () => ({
  getMe: vi.fn().mockResolvedValue(null),
  listUsers: vi.fn().mockResolvedValue([]),
}));

vi.mock("@/components/settings/model-status-panel", () => ({
  ModelStatusPanel: () => <div data-testid="model-status-panel">Models</div>,
}));

function setupAutonomousMocks() {
  vi.mocked(getAutonomousHistory).mockResolvedValue(mockHistory);
  vi.mocked(stopAutonomousCycle).mockResolvedValue({
    status: "stopped",
    cycle_id: "auto_20260502_143000",
  });
  vi.mocked(triggerAutonomous).mockResolvedValue({
    cycle_id: "auto_20260502_160000",
    status: "running",
    domain: "AI/NLP",
    max_runs: 3,
  });
  vi.mocked(getEvolutionStatus).mockResolvedValue(mockEvolutionStatus);
  vi.mocked(startScheduler).mockResolvedValue({ status: "running", interval_seconds: 3600 });
  vi.mocked(stopScheduler).mockResolvedValue({ status: "stopped" });
  vi.mocked(getSchedulerStatus).mockResolvedValue(mockSchedulerStatus);
  // The migrated page calls getConsciousnessState on mount via useQuery.
  vi.mocked(getConsciousnessState).mockResolvedValue({ state: "idle", seconds_in_state: 0, next_action: "" });
}

function setupSettingsMocks() {
  vi.mocked(getEvolutionStatus).mockResolvedValue(mockEvolutionStatus);
}

// ── Helpers ────────────────────────────────────────────────────

function renderSettings() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AuthProvider>
          <SettingsProvider>
            <Settings />
          </SettingsProvider>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function renderAutonomousPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/autonomous"]}>
        <AuthProvider>
          <Routes>
            <Route path="/autonomous" element={<AutonomousPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("BATCH-27/TASK-02: Self-Improvement Settings + Scheduler Controls", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  // ── TEST-27-02-01: Settings shows self-improve section (read-only) ──
  it("TEST-27-02-01: Settings shows self-improve section (read-only)", async () => {
    setupSettingsMocks();
    renderSettings();

    // Expand Advanced section
    await waitFor(() => {
      expect(screen.getByTestId("advanced-toggle")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByTestId("advanced-toggle"));

    await waitFor(() => {
      expect(screen.getByTestId("self-improve-section")).toBeInTheDocument();
    });

    expect(screen.getByText("Self-Improvement")).toBeInTheDocument();
    expect(screen.getByTestId("evolution-enabled-status")).toHaveTextContent("Enabled");
    expect(screen.getByTestId("evolution-overlay-count")).toHaveTextContent("5");
    expect(screen.getByTestId("evolution-outcome-count")).toHaveTextContent("2");

    // Verify outcomes list renders
    expect(screen.getByTestId("evolution-outcomes-list")).toBeInTheDocument();
  });

  // ── TEST-27-02-02: Autonomous page shows scheduler start/stop ──
  it("TEST-27-02-02: Autonomous page shows scheduler start/stop", async () => {
    setupAutonomousMocks();
    renderAutonomousPage();

    await waitFor(() => {
      expect(screen.getByTestId("autonomous-page")).toBeInTheDocument();
    });

    expect(screen.getByTestId("scheduler-controls")).toBeInTheDocument();
    expect(screen.getByTestId("scheduler-start-btn")).toBeInTheDocument();
    expect(screen.getByTestId("scheduler-stop-btn")).toBeInTheDocument();
  });

  // ── TEST-27-02-03: Evolution status displayed ──
  it("TEST-27-02-03: Evolution status displayed", async () => {
    setupAutonomousMocks();
    renderAutonomousPage();

    // Wait for the evolution query to resolve and render its data.
    // The card exists immediately (page shell), but the data-driven
    // content ("Yes", "5", "2") only appears after the query resolves.
    await waitFor(() => {
      expect(screen.getByTestId("evolution-enabled")).toHaveTextContent("Yes");
    });

    expect(screen.getByTestId("evolution-overlays")).toHaveTextContent("5");
    expect(screen.getByTestId("evolution-outcomes")).toHaveTextContent("2");
  });

  // ── TEST-27-02-04: Scheduler start calls API ──
  it("TEST-27-02-04: Scheduler start calls API", async () => {
    setupAutonomousMocks();
    renderAutonomousPage();

    await waitFor(() => {
      expect(screen.getByTestId("scheduler-start-btn")).toBeInTheDocument();
    });

    const startBtn = screen.getByTestId("scheduler-start-btn");
    await userEvent.click(startBtn);

    await waitFor(() => {
      expect(startScheduler).toHaveBeenCalledTimes(1);
    });
  });

  // ── TEST-27-02-05: Scheduler stop calls API ──
  it("TEST-27-02-05: Scheduler stop calls API", async () => {
    setupAutonomousMocks();
    // Set scheduler as running so stop button is enabled
    vi.mocked(getSchedulerStatus).mockResolvedValue({ status: "running", next_run: "2026-05-02T16:00:00Z" });

    renderAutonomousPage();

    // Wait for the scheduler query to resolve and the stop button to enable.
    // The button exists immediately but is disabled until status === "running".
    await waitFor(() => {
      expect(screen.getByTestId("scheduler-stop-btn")).not.toBeDisabled();
    });

    const stopBtn = screen.getByTestId("scheduler-stop-btn");
    await userEvent.click(stopBtn);

    await waitFor(() => {
      expect(stopScheduler).toHaveBeenCalledTimes(1);
    });
  });

  // ── TEST-27-02-06: Scheduler status displayed ──
  it("TEST-27-02-06: Scheduler status displayed", async () => {
    setupAutonomousMocks();
    renderAutonomousPage();

    // Wait for the scheduler query data to render, not just the element.
    await waitFor(() => {
      expect(screen.getByTestId("scheduler-status-text")).toHaveTextContent("stopped");
    });
  });

  // ── TEST-27-02-07: No edit controls for evolution params (HB-01) ──
  it("TEST-27-02-07: No edit controls for evolution params (HB-01)", async () => {
    setupSettingsMocks();
    renderSettings();

    // Expand Advanced section
    await waitFor(() => {
      expect(screen.getByTestId("advanced-toggle")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByTestId("advanced-toggle"));

    await waitFor(() => {
      expect(screen.getByTestId("self-improve-section")).toBeInTheDocument();
    });

    // Verify NO input/button controls inside self-improve section
    const section = screen.getByTestId("self-improve-section");
    const inputs = section.querySelectorAll("input");
    const buttons = section.querySelectorAll("button");
    const selects = section.querySelectorAll("select");

    expect(inputs.length).toBe(0);
    expect(buttons.length).toBe(0);
    expect(selects.length).toBe(0);

    // Verify the read-only notice is present
    expect(
      screen.getByText("Evolution parameters are managed by the system and cannot be edited.")
    ).toBeInTheDocument();
  });
});
