/**
 * Tests for BATCH-21/TASK-01: Traces API Client
 *
 * TEST-21-01-01 through TEST-21-01-03
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { getTraceSummary, getTrace, getTraceMetrics } from "@/api/traces";
import type { TraceSummary, TraceDetail, TraceMetrics } from "@/api/traces";
import { apiFetchJson } from "@/api/client";

// F1.7a: all three trace functions now route through callContract → apiFetchJson.
vi.mock("@/api/client", () => ({
  apiFetchJson: vi.fn(),
  apiFetchUnchecked: vi.fn(),
}));

const mockApiFetchJson = vi.mocked(apiFetchJson);

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
      recent_traces: [
        {
          trace_id: "abc123",
          span_count: 12,
          duration_ms: 120000,
          last_activity: Date.now() / 1000,
          error_count: 0,
          models: ["glm-5.2"],
        },
      ],
    };
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await getTraceSummary();

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/traces/summary",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual(expected);
    expect(result.total_traces).toBe(42);
    expect(result.active_traces).toBe(3);
    expect(result.error_rate).toBe(0.05);
    expect(result.recent_traces[0]!.trace_id).toBe("abc123");
  });

  // ── TEST-21-01-01b: summary decoder rejects missing recent_traces ──
  it("getTraceSummary() rejects a payload without recent_traces", async () => {
    mockApiFetchJson.mockResolvedValueOnce({
      total_traces: 1,
      active_traces: 0,
      error_rate: 0,
    });
    await expect(getTraceSummary()).rejects.toThrow(/recent_traces/);
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
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await getTrace("abc-123");

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/traces/trace/abc-123",
      expect.objectContaining({ method: "GET" }),
    );
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
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await getTraceMetrics();

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/traces/metrics",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual(expected);
    expect(result.p50_ms).toBe(120);
    expect(result.p99_ms).toBe(3500);
    expect(result.error_rate).toBe(0.02);
  });
});
