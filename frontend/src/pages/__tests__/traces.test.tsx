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

const mockSummary = {
  total_traces: 5,
  active_traces: 2,
  error_rate: 0.05,
};

const mockMetrics = {
  p50_ms: 120,
  p99_ms: 3500,
  error_rate: 0.02,
};

const mockTraceDetail = {
  trace_id: "trace-1",
  spans: [
    { name: "generation", duration_ms: 1500 },
    { name: "evaluation", duration_ms: 800 },
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
    expect(screen.getByTestId("total-traces")).toHaveTextContent("5");
    expect(screen.getByTestId("active-traces")).toHaveTextContent("2");
  });

  // ── TEST-21-02-02: Trace list loads from summary ───────────
  it("TEST-21-02-02: Trace list loads from summary", async () => {
    setupMocks();
    renderTracesPage();

    await waitFor(() => {
      expect(screen.getByTestId("traces-list")).toBeInTheDocument();
    });

    // 5 traces listed from summary.total_traces
    expect(screen.getByTestId("trace-item-trace-1")).toBeInTheDocument();
    expect(screen.getByTestId("trace-item-trace-5")).toBeInTheDocument();

    // First 2 are active
    expect(screen.getByTestId("trace-item-trace-1").textContent).toContain("Active");
    expect(screen.getByTestId("trace-item-trace-2").textContent).toContain("Active");
  });

  // ── TEST-21-02-03: Click trace shows span detail ───────────
  it("TEST-21-02-03: Click trace shows span detail", async () => {
    setupMocks();
    renderTracesPage();

    await waitFor(() => {
      expect(screen.getByTestId("trace-item-trace-1")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByTestId("trace-item-trace-1"));

    await waitFor(() => {
      expect(screen.getByTestId("traces-span-detail")).toBeInTheDocument();
    });

    expect(getTrace).toHaveBeenCalledWith("trace-1");
    expect(screen.getByTestId("span-trace-id")).toHaveTextContent("trace-1");
    expect(screen.getByTestId("span-name-0")).toHaveTextContent("generation");
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
