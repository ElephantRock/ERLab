/**
 * Tests for BATCH-21/TASK-01: Traces API Client
 *
 * TEST-21-01-01 through TEST-21-01-03
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { getTraceSummary, getTrace, getTraceMetrics } from "@/api/traces";
import type { TraceSummary, TraceDetail, TraceMetrics } from "@/api/traces";
import { apiFetchUnchecked } from "@/api/client";

vi.mock("@/api/client", () => ({
  apiFetchUnchecked: vi.fn(),
}));

const mockApiFetch = vi.mocked(apiFetchUnchecked);

describe("BATCH-21/TASK-01: Traces API Client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── TEST-21-01-01: getTraceSummary() correct endpoint ──────
  it("TEST-21-01-01: getTraceSummary() calls correct endpoint", async () => {
    const expected: TraceSummary = {
      total_traces: 42,
      active_traces: 3,
      error_rate: 0.05,
    };
    mockApiFetch.mockResolvedValueOnce(expected);

    const result = await getTraceSummary();

    expect(mockApiFetch).toHaveBeenCalledWith("/traces/summary");
    expect(result).toEqual(expected);
    expect(result.total_traces).toBe(42);
    expect(result.active_traces).toBe(3);
    expect(result.error_rate).toBe(0.05);
  });

  // ── TEST-21-01-02: getTrace(id) correct endpoint ──────────
  it("TEST-21-01-02: getTrace(id) calls correct endpoint", async () => {
    const expected: TraceDetail = {
      trace_id: "abc-123",
      spans: [
        { name: "generation", duration_ms: 1500 },
        { name: "evaluation", duration_ms: 800 },
      ],
    };
    mockApiFetch.mockResolvedValueOnce(expected);

    const result = await getTrace("abc-123");

    expect(mockApiFetch).toHaveBeenCalledWith("/traces/trace/abc-123");
    expect(result).toEqual(expected);
    expect(result.trace_id).toBe("abc-123");
    expect(result.spans).toHaveLength(2);
    expect(result.spans[0].name).toBe("generation");
    expect(result.spans[0].duration_ms).toBe(1500);
  });

  // ── TEST-21-01-03: getTraceMetrics() correct endpoint ─────
  it("TEST-21-01-03: getTraceMetrics() calls correct endpoint", async () => {
    const expected: TraceMetrics = {
      p50_ms: 120,
      p99_ms: 3500,
      error_rate: 0.02,
    };
    mockApiFetch.mockResolvedValueOnce(expected);

    const result = await getTraceMetrics();

    expect(mockApiFetch).toHaveBeenCalledWith("/traces/metrics");
    expect(result).toEqual(expected);
    expect(result.p50_ms).toBe(120);
    expect(result.p99_ms).toBe(3500);
    expect(result.error_rate).toBe(0.02);
  });
});
