/**
 * Traces API Client — BATCH-21/TASK-01
 *
 * Typed functions for trace observability endpoints.
 * Endpoint shapes from backend/api/routes/traces.py:
 *   GET /traces/summary     → {total_traces, active_traces, error_rate}
 *   GET /traces/trace/{id}  → {trace_id, spans: [{name, duration_ms, ...}]}
 *   GET /traces/metrics     → {p50_ms, p99_ms, error_rate}
 */

import { apiFetchUnchecked } from "./client";

// ── Types ────────────────────────────────────────────────────────

export interface TraceSummary {
  total_traces: number;
  active_traces: number;
  error_rate: number;
}

export interface TraceSpan {
  name: string;
  duration_ms: number;
  [key: string]: unknown;
}

export interface TraceDetail {
  trace_id: string;
  spans: TraceSpan[];
}

export interface TraceMetrics {
  p50_ms: number;
  p99_ms: number;
  error_rate: number;
}

// ── API Functions ────────────────────────────────────────────────

export function getTraceSummary(): Promise<TraceSummary> {
  return apiFetchUnchecked<TraceSummary>("/traces/summary");
}

export function getTrace(traceId: string): Promise<TraceDetail> {
  return apiFetchUnchecked<TraceDetail>(`/traces/trace/${traceId}`);
}

export function getTraceMetrics(): Promise<TraceMetrics> {
  return apiFetchUnchecked<TraceMetrics>("/traces/metrics");
}
