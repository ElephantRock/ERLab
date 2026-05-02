/**
 * Tests for BATCH-21/TASK-01: Trace Components
 *
 * TEST-21-01-04: TraceSummary renders stats
 * TEST-21-01-05: SpanDetail renders span data
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TraceSummary } from "@/components/traces/trace-summary";
import { SpanDetail } from "@/components/traces/span-detail";
import type { TraceSummary as TraceSummaryData, TraceSpan } from "@/api/traces";

// ── Shared fixtures ────────────────────────────────────────

const mockSummary: TraceSummaryData = {
  total_traces: 42,
  active_traces: 3,
  error_rate: 0.05,
};

const mockSpans: TraceSpan[] = [
  { name: "generation", duration_ms: 1500 },
  { name: "evaluation", duration_ms: 800 },
  { name: "validation", duration_ms: 250 },
];

// ── TEST-21-01-04: TraceSummary renders stats ──────────────

describe("TraceSummary", () => {
  it("TEST-21-01-04: TraceSummary renders stats", () => {
    render(<TraceSummary summary={mockSummary} />);

    expect(screen.getByTestId("trace-summary")).toBeInTheDocument();
    expect(screen.getByTestId("total-traces")).toHaveTextContent("42");
    expect(screen.getByTestId("active-traces")).toHaveTextContent("3");
    expect(screen.getByTestId("error-rate")).toHaveTextContent("5.0%");
  });

  it("formats large numbers with locale formatting", () => {
    const largeSummary: TraceSummaryData = {
      total_traces: 12345,
      active_traces: 100,
      error_rate: 0.123,
    };
    render(<TraceSummary summary={largeSummary} />);

    expect(screen.getByTestId("total-traces")).toHaveTextContent("12,345");
    expect(screen.getByTestId("active-traces")).toHaveTextContent("100");
    expect(screen.getByTestId("error-rate")).toHaveTextContent("12.3%");
  });
});

// ── TEST-21-01-05: SpanDetail renders span data ────────────

describe("SpanDetail", () => {
  it("TEST-21-01-05: SpanDetail renders span data", () => {
    render(<SpanDetail spans={mockSpans} traceId="abc-123" />);

    expect(screen.getByTestId("span-detail")).toBeInTheDocument();
    expect(screen.getByTestId("span-trace-id")).toHaveTextContent("abc-123");

    // Check first span
    expect(screen.getByTestId("span-name-0")).toHaveTextContent("generation");
    expect(screen.getByTestId("span-duration-0")).toHaveTextContent("1.50s");

    // Check second span
    expect(screen.getByTestId("span-name-1")).toHaveTextContent("evaluation");
    expect(screen.getByTestId("span-duration-1")).toHaveTextContent("800ms");

    // Check third span
    expect(screen.getByTestId("span-name-2")).toHaveTextContent("validation");
    expect(screen.getByTestId("span-duration-2")).toHaveTextContent("250ms");
  });

  it("renders empty spans list", () => {
    render(<SpanDetail spans={[]} traceId="empty-trace" />);

    expect(screen.getByTestId("span-detail")).toBeInTheDocument();
    expect(screen.getByTestId("span-trace-id")).toHaveTextContent("empty-trace");
  });
});
