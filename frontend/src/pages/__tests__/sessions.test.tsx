/**
 * Tests for BATCH-22/TASK-02: Sessions Page & Pipeline Session Input
 *
 * TEST-22-02-01 through TEST-22-02-07
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SessionsPage from "@/pages/sessions";
import PipelineNew from "@/pages/pipeline-new";

// ── Mock APIs ──────────────────────────────────────────────────

const mockSessions = [
  { session_id: "sess-alpha", run_count: 3, latest_run_at: "2026-05-02T14:30:00Z" },
  { session_id: "sess-beta", run_count: 1, latest_run_at: "2026-05-02T10:00:00Z" },
];

const mockRuns = {
  runs: [
    { id: 1, status: "completed", domain: "AI/NLP", current_stage: "done", ideas_count: 5, session_id: "sess-alpha", created_at: "2026-05-02T14:30:00Z", completed_at: "2026-05-02T14:45:00Z", error_message: null },
    { id: 2, status: "running", domain: "AI/ML", current_stage: "generation", ideas_count: 0, session_id: "sess-alpha", created_at: "2026-05-02T14:32:00Z", completed_at: null, error_message: null },
  ],
  total: 2,
};

vi.mock("@/api/sessions", () => ({
  getSessionList: vi.fn(),
}));

vi.mock("@/api/pipeline", () => ({
  triggerRun: vi.fn(),
  listRuns: vi.fn(),
  getRunIdeas: vi.fn(),
  cancelRun: vi.fn(),
  getEstimate: vi.fn().mockResolvedValue({
    strategy: "fast_scan",
    stages: 3,
    estimated_cost_usd: 0,
    estimated_time_seconds: 120,
    estimated_time_display: "~2 min",
    cost_display: "$0.00",
    local_cost_usd: 0,
    cloud_cost_usd: 0,
    breakdown: [],
  }),
}));

vi.mock("@/hooks/usePipelineProgress", () => ({
  usePipelineProgress: () => ({ stages: [], isComplete: false, isConnected: false }),
}));

vi.mock("@/api/status", () => ({
  getSystemStatus: vi.fn().mockResolvedValue({
    app_name: "Elephant Rock Research",
    version: "0.1.0",
    config: { default_provider: "lmstudio", governance_enabled: true, memory_enabled: true },
    defaults: {},
  }),
}));

import { getSessionList } from "@/api/sessions";
import { listRuns } from "@/api/pipeline";

// ── Helpers ────────────────────────────────────────────────────

function renderSessionsPage() {
  return render(
    <MemoryRouter initialEntries={["/sessions"]}>
      <Routes>
        <Route path="/sessions" element={<SessionsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function renderPipelinePage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/pipeline/new"]}>
        <Routes>
          <Route path="/pipeline/new" element={<PipelineNew />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("BATCH-22/TASK-02: Sessions Page + Pipeline Session Input", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── TEST-22-02-01: Sessions page renders grouped runs ────────
  it("TEST-22-02-01: Sessions page renders grouped runs", async () => {
    vi.mocked(getSessionList).mockResolvedValue({ sessions: mockSessions });

    renderSessionsPage();

    await waitFor(() => {
      expect(screen.getByTestId("sessions-page")).toBeInTheDocument();
    });

    // Both sessions should be rendered
    expect(screen.getByTestId("session-card-sess-alpha")).toBeInTheDocument();
    expect(screen.getByTestId("session-card-sess-beta")).toBeInTheDocument();
  });

  // ── TEST-22-02-02: Click session shows filtered runs ─────────
  it("TEST-22-02-02: Click session shows filtered runs", async () => {
    vi.mocked(getSessionList).mockResolvedValue({ sessions: mockSessions });
    vi.mocked(listRuns).mockResolvedValue(mockRuns);

    renderSessionsPage();

    await waitFor(() => {
      expect(screen.getByTestId("session-card-sess-alpha")).toBeInTheDocument();
    });

    // Click on the first session card
    await userEvent.click(screen.getByTestId("session-card-sess-alpha"));

    // listRuns should be called with session_id filter
    await waitFor(() => {
      expect(listRuns).toHaveBeenCalledWith({ session_id: "sess-alpha", limit: 50 });
    });

    // Runs should be displayed
    await waitFor(() => {
      expect(screen.getByTestId("sessions-runs-list")).toBeInTheDocument();
    });

    expect(screen.getByTestId("session-run-1")).toBeInTheDocument();
    expect(screen.getByTestId("session-run-2")).toBeInTheDocument();
  });

  // ── TEST-22-02-03: Pipeline form has session_id input ────────
  it("TEST-22-02-03: Pipeline form has session_id input", async () => {
    const user = userEvent.setup();
    renderPipelinePage();

    // Open advanced section to access session input
    await user.click(screen.getByTestId("advanced-toggle"));
    const sessionInput = screen.getByTestId("session-id-input");
    expect(sessionInput).toBeInTheDocument();
    expect(sessionInput).toHaveAttribute("placeholder", "my-session-name");
  });

  // ── TEST-22-02-04: Session card shows run count and latest date
  it("TEST-22-02-04: Session card shows run count and latest date", async () => {
    vi.mocked(getSessionList).mockResolvedValue({ sessions: mockSessions });

    renderSessionsPage();

    await waitFor(() => {
      expect(screen.getByTestId("session-count-sess-alpha")).toBeInTheDocument();
    });

    expect(screen.getByTestId("session-count-sess-alpha")).toHaveTextContent("3 runs");
    expect(screen.getByTestId("session-count-sess-beta")).toHaveTextContent("1 run");
    expect(screen.getByTestId("session-date-sess-alpha")).toBeInTheDocument();
    expect(screen.getByTestId("session-date-sess-beta")).toBeInTheDocument();
  });

  // ── TEST-22-02-05: Empty sessions shows message ──────────────
  it("TEST-22-02-05: Empty sessions shows message", async () => {
    vi.mocked(getSessionList).mockResolvedValue({ sessions: [] });

    renderSessionsPage();

    await waitFor(() => {
      expect(screen.getByTestId("sessions-empty")).toBeInTheDocument();
    });

    expect(screen.getByText(/No sessions yet/)).toBeInTheDocument();
  });

  // ── TEST-22-02-06: Session input is optional ─────────────────
  it("TEST-22-02-06: New session input is optional", async () => {
    const user = userEvent.setup();
    renderPipelinePage();

    // Open advanced section to access session input
    await user.click(screen.getByTestId("advanced-toggle"));
    const sessionInput = screen.getByTestId("session-id-input") as HTMLInputElement;
    expect(sessionInput.value).toBe("");

    // Verify the label indicates optional
    expect(screen.getByText("Session ID (optional)")).toBeInTheDocument();
  });

  // ── TEST-22-02-07: API error handled ─────────────────────────
  it("TEST-22-02-07: API error handled", async () => {
    vi.mocked(getSessionList).mockRejectedValue(new Error("Network failure"));

    renderSessionsPage();

    await waitFor(() => {
      expect(screen.getByTestId("sessions-error")).toBeInTheDocument();
    });

    expect(screen.getByText("Error loading sessions")).toBeInTheDocument();
  });
});
