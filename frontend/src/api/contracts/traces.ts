/**
 * F1.7a — Trace observability endpoint contracts.
 *
 * Migrates the three trace endpoints in src/api/traces.ts from
 * apiFetchUnchecked to JsonContract with runtime decoders.
 *
 * Backend sources (backend/api/routes/traces.py):
 *   GET /traces/summary    → { total_traces, active_traces, error_rate,
 *                              recent_traces: RecentTrace[] (real ids,
 *                              newest first) }
 *   GET /traces/trace/{id} → { trace_id, spans: TraceSpan[] }
 *   GET /traces/metrics    → { p50_ms, p99_ms, error_rate, p95_ms?, avg_ms?,
 *                              call_count?, by_kind? }
 *
 * TraceSpan has an open shape ([key: string]: unknown) — only the material
 * name + duration_ms are validated; the remaining per-span fields are
 * preserved via decodeObject's forward-compat spread.
 */

import {
  decodeArray,
  decodeNumber,
  decodeObject,
  decodeString,
  type JsonContract,
  type ResponseDecoder,
} from "./common";
import type {
  RecentTrace,
  TraceDetail,
  TraceMetrics,
  TraceSummary,
} from "@/api/traces";

// ── Decoders ─────────────────────────────────────────────────────────

const recentTraceDecoder: ResponseDecoder<RecentTrace> = decodeObject<RecentTrace>({
  required: {
    trace_id: decodeString,
    span_count: decodeNumber,
    duration_ms: decodeNumber,
  },
  optional: {
    started_at: decodeNumber,
    last_activity: decodeNumber,
    error_count: decodeNumber,
    models: decodeArray(decodeString),
  },
});

export const traceSummaryDecoder = decodeObject<TraceSummary>({
  required: {
    total_traces: decodeNumber,
    active_traces: decodeNumber,
    error_rate: decodeNumber,
    recent_traces: decodeArray(recentTraceDecoder),
  },
});

// TraceSpan has an open shape ([key: string]: unknown). Validate the two
// material fields (name for display, duration_ms for latency) and preserve
// the rest via the spread.
const traceSpanDecoder = decodeObject<{ name: string; duration_ms: number; [key: string]: unknown }>({
  required: {
    name: decodeString,
    duration_ms: decodeNumber,
  },
});

const traceDetailDecoder = decodeObject<TraceDetail>({
  required: {
    trace_id: decodeString,
    spans: decodeArray(traceSpanDecoder),
  },
});

export const traceMetricsDecoder = decodeObject<TraceMetrics>({
  required: {
    p50_ms: decodeNumber,
    p99_ms: decodeNumber,
    error_rate: decodeNumber,
  },
  optional: {
    p95_ms: decodeNumber,
    avg_ms: decodeNumber,
    call_count: decodeNumber,
    by_kind: decodeObject<Record<string, unknown>>({}),
  },
});

// ── Contracts ────────────────────────────────────────────────────────

export const getTraceSummaryContract: JsonContract<TraceSummary> = {
  id: "traces.getTraceSummary",
  method: "GET",
  pathPattern: "/traces/summary",
  responseKind: "json",
  decoder: traceSummaryDecoder,
};

export const getTraceContract: JsonContract<TraceDetail> = {
  id: "traces.getTrace",
  method: "GET",
  pathPattern: "/traces/trace/{traceId}",
  responseKind: "json",
  decoder: traceDetailDecoder,
};

export const getTraceMetricsContract: JsonContract<TraceMetrics> = {
  id: "traces.getTraceMetrics",
  method: "GET",
  pathPattern: "/traces/metrics",
  responseKind: "json",
  decoder: traceMetricsDecoder,
};
