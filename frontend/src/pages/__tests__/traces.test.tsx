/**
 * Tests for BATCH-21/TASK-02: Traces Viewer Page
 *
 * TEST-21-02-01 through TEST-21-02-07
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import TracesPage from "@/pages/traces";

// ── Mock the traces API ──────────────────────────────────────────

const NOW_SECONDS = Date.now() / 1000;

const mockSummary = {
  total_traces: 2,
  active_traces: 1,
  error_rate: 0.05,
  recent_traces: [
    {
      trace_id: "abc123def456",
      span_count: 4,
      duration_ms: 9000,
      started_at: NOW_SECONDS - 10,
      last_activity: NOW_SECONDS - 5,
      error_count: 0,
      models: ["glm-5.2"],
    },
    {
      trace_id: "old789",
      span_count: 2,
      duration_ms: 1500,
      started_at: NOW_SECONDS - 7200,
      last_activity: NOW_SECONDS - 7000,
      error_count: 1,
      models: [],
    },
  ],
};

const mockMetrics = {
  p50_ms: 120,
  p99_ms: 3500,
  error_rate: 0.02,
};

const mockTraceDetail = {
  trace_id: "abc123def456",
  spans: [
    { name: "generation", duration_ms: 1500, kind: "stage", status: "ok" },
    { name: "evaluation", duration_ms: 800, kind: "llm_call", status: "ok" },
  ],
};

vi.mock("@/api/traces", () => ({
  getTraceSummary: vi.fn(),
  getTrace: vi.fn(),
  getTraceMetrics: vi.fn(),
}));

import {
  getTraceSummary,
  getTrace,
  getTraceMetrics,
} from "@/api/traces";

function setupMocks() {
  vi.mocked(getTraceSummary).mockResolvedValue(mockSummary);
  vi.mocked(getTraceMetrics).mockResolvedValue(mockMetrics);
  vi.mocked(getTrace).mockResolvedValue(mockTraceDetail);
}

// ── Helper ───────────────────────────────────────────────────────

function renderTracesPage() {
  return render(
    <MemoryRouter initialEntries={["/traces"]}>
      <Routes>
        <Route path="/traces" element={<TracesPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("BATCH-21/TASK-02: Traces Viewer Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── TEST-21-02-01: Page renders summary ────────────────────
  it("TEST-21-02-01: Page renders summary", async () => {
    setupMocks();
    renderTracesPage();

    await waitFor(() => {
      expect(screen.getByTestId("traces-page")).toBeInTheDocument();
    });

    expect(screen.getByText("Traces")).toBeInTheDocument();
    expect(screen.getByTestId("traces-summary-section")).toBeInTheDocument();
    expect(screen.getByTestId("total-traces")).toHaveTextContent("2");
    expect(screen.getByTestId("active-traces")).toHaveTextContent("1");
  });

  // ── TEST-21-02-02: Trace list renders REAL trace ids from summary ──
  it("TEST-21-02-02: Trace list renders real trace ids from summary", async () => {
    setupMocks();
    renderTracesPage();

    await waitFor(() => {
      expect(screen.getByTestId("traces-list")).toBeInTheDocument();
    });

    // Both traces listed by their real ids (no fabricated trace-N ids).
    expect(screen.getByTestId("trace-item-abc123def456")).toBeInTheDocument();
    expect(screen.getByTestId("trace-item-old789")).toBeInTheDocument();
    expect(screen.queryByTestId("trace-item-trace-1")).not.toBeInTheDocument();

    // Recently-active trace shows the Active badge; the stale one shows an
    // error badge instead.
    expect(screen.getByTestId("trace-item-abc123def456").textContent).toContain("Active");
    expect(screen.getByTestId("trace-item-old789").textContent).toContain("1 err");
    // Model attribution is surfaced on the list rows.
    expect(screen.getByTestId("trace-item-abc123def456").textContent).toContain("glm-5.2");
  });

  // ── TEST-21-02-03: Click trace shows span detail ───────────
  it("TEST-21-02-03: Click trace shows span detail", async () => {
    setupMocks();
    renderTracesPage();

    await waitFor(() => {
      expect(screen.getByTestId("trace-item-abc123def456")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByTestId("trace-item-abc123def456"));

    await waitFor(() => {
      expect(screen.getByTestId("traces-span-detail")).toBeInTheDocument();
    });

    expect(getTrace).toHaveBeenCalledWith("abc123def456");
    expect(screen.getByTestId("span-trace-id")).toHaveTextContent("abc123def456");
    expect(screen.getByTestId("span-name-0")).toHaveTextContent("generation");
  });

  // ── TEST-21-02-03b: Detail load failure is visible, not swallowed ──
  it("TEST-21-02-03b: Detail load failure surfaces inline error", async () => {
    setupMocks();
    vi.mocked(getTrace).mockRejectedValue(new Error("No spans found for trace abc123def456"));
    renderTracesPage();

    await waitFor(() => {
      expect(screen.getByTestId("trace-item-abc123def456")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByTestId("trace-item-abc123def456"));

    await waitFor(() => {
      expect(screen.getByTestId("trace-detail-error")).toBeInTheDocument();
    });
    expect(screen.getByTestId("trace-detail-error").textContent).toContain(
      "No spans found",
    );
  });

  // ── TEST-21-02-04: Latency metrics displayed ───────────────
  it("TEST-21-02-04: Latency metrics displayed", async () => {
    setupMocks();
    renderTracesPage();

    await waitFor(() => {
      expect(screen.getByTestId("traces-metrics")).toBeInTheDocument();
    });

    expect(screen.getByTestId("metric-p50")).toHaveTextContent("120ms");
    expect(screen.getByTestId("metric-p99")).toHaveTextContent("3.50s");
    expect(screen.getByTestId("metric-error-rate")).toHaveTextContent("2.0%");
  });

  // ── TEST-21-02-05: Error state handled ─────────────────────
  it("TEST-21-02-05: Error state handled", async () => {
    vi.mocked(getTraceSummary).mockRejectedValue(new Error("Network failure"));
    vi.mocked(getTraceMetrics).mockRejectedValue(new Error("Network failure"));

    renderTracesPage();

    await waitFor(() => {
      expect(screen.getByTestId("traces-error")).toBeInTheDocument();
    });

    expect(screen.getByText("Error loading trace data")).toBeInTheDocument();
  });

  // ── TEST-21-02-06: Empty state shown ───────────────────────
  it("TEST-21-02-06: Empty state shown", async () => {
    vi.mocked(getTraceSummary).mockResolvedValue({
      total_traces: 0,
      active_traces: 0,
      error_rate: 0,
      recent_traces: [],
    });
    vi.mocked(getTraceMetrics).mockResolvedValue({
      p50_ms: 0,
      p99_ms: 0,
      error_rate: 0,
    });

    renderTracesPage();

    await waitFor(() => {
      expect(screen.getByTestId("traces-empty")).toBeInTheDocument();
    });

    expect(screen.getByText(/No traces recorded yet/)).toBeInTheDocument();
  });

  // ── TEST-21-02-07: Service unavailable shows message ────────
  it("TEST-21-02-07: Service unavailable shows message", async () => {
    vi.mocked(getTraceSummary).mockRejectedValue(
      new Error("Observability not enabled"),
    );
    vi.mocked(getTraceMetrics).mockRejectedValue(
      new Error("Observability not enabled"),
    );

    renderTracesPage();

    await waitFor(() => {
      expect(screen.getByTestId("traces-service-unavailable")).toBeInTheDocument();
    });

    expect(screen.getByText("Observability Not Enabled")).toBeInTheDocument();
    expect(screen.getByText(/Enable observability/)).toBeInTheDocument();
  });
});
