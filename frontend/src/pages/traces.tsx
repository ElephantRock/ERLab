/**
 * TracesPage — BATCH-21/TASK-02
 *
 * Traces viewer page replacing /traces placeholder.
 * Shows: summary stats, latency metrics, trace list, and span detail on click.
 */

import { useEffect, useState, useCallback } from "react";
import {
  getTraceSummary,
  getTrace,
  getTraceMetrics,
} from "@/api/traces";
import type {
  TraceSummary as TraceSummaryData,
  TraceDetail,
  TraceMetrics as TraceMetricsData,
  RecentTrace,
} from "@/api/traces";
import { TraceSummary } from "@/components/traces/trace-summary";
import { SpanDetail } from "@/components/traces/span-detail";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Activity } from "lucide-react";

/** A trace is shown as Active while its latest span ended within this window. */
const ACTIVE_BADGE_WINDOW_MS = 60_000;

export default function TracesPage() {
  const [summary, setSummary] = useState<TraceSummaryData | null>(null);
  const [metrics, setMetrics] = useState<TraceMetricsData | null>(null);
  const [selectedTrace, setSelectedTrace] = useState<TraceDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Captured in the load effect — never read Date.now() during render.
  const [loadedAtMs, setLoadedAtMs] = useState(0);
  const [loading, setLoading] = useState(true);
  const [serviceUnavailable, setServiceUnavailable] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [sum, met] = await Promise.all([
          getTraceSummary(),
          getTraceMetrics(),
        ]);
        if (cancelled) return;

        setSummary(sum);
        setMetrics(met);
        setLoadedAtMs(Date.now());
        setError(null);
        setServiceUnavailable(false);
      } catch (err) {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : String(err);
        if (message.toLowerCase().includes("observability not enabled") ||
            message.toLowerCase().includes("service unavailable")) {
          setServiceUnavailable(true);
        }
        setError(message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, []);

  const handleTraceClick = useCallback(async (traceId: string) => {
    setDetailError(null);
    try {
      const detail = await getTrace(traceId);
      setSelectedTrace(detail);
    } catch (err) {
      // Surfaced inline next to the list — a failed click must not look
      // like a no-op (PRODUCT.md §6: if data failed to load, it says so).
      setSelectedTrace(null);
      setDetailError(
        err instanceof Error ? err.message : String(err),
      );
    }
  }, []);

  const formatDuration = (ms: number): string => {
    if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`;
    return `${ms.toFixed(0)}ms`;
  };

  if (loading) {
    return (
      <div className="space-y-6" data-testid="traces-page">
        <h1 className="text-2xl font-bold tracking-tight">Traces</h1>
        <div className="space-y-3" data-testid="traces-loading">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      </div>
    );
  }

  if (serviceUnavailable) {
    return (
      <div className="space-y-6" data-testid="traces-page">
        <h1 className="text-2xl font-bold tracking-tight">Traces</h1>
        <div className="rounded-lg border border-warning/30 bg-warning/5 p-4 text-warning" data-testid="traces-service-unavailable">
          <p className="font-medium">Observability Not Enabled</p>
          <p className="text-sm">Enable observability in platform configuration to view traces.</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6" data-testid="traces-page">
        <h1 className="text-2xl font-bold tracking-tight">Traces</h1>
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-destructive" data-testid="traces-error">
          <p className="font-medium">Error loading trace data</p>
          <p className="text-sm">{error}</p>
        </div>
      </div>
    );
  }

  const isEmpty = summary !== null && summary.total_traces === 0;

  return (
    <div className="space-y-6" data-testid="traces-page">
      <h1 className="text-2xl font-bold tracking-tight">Traces</h1>

      {/* Summary stats */}
      {summary && (
        <div data-testid="traces-summary-section">
          <TraceSummary summary={summary} />
        </div>
      )}

      {/* Latency metrics */}
      {metrics && (
        <div className="rounded-lg border bg-card p-6" data-testid="traces-metrics">
          <h3 className="text-sm font-medium text-muted-foreground mb-4">Latency Metrics</h3>
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <p className="text-2xl font-bold" data-testid="metric-p50">
                {formatDuration(metrics.p50_ms)}
              </p>
              <p className="text-sm text-muted-foreground">P50 Latency</p>
            </div>
            <div>
              <p className="text-2xl font-bold" data-testid="metric-p99">
                {formatDuration(metrics.p99_ms)}
              </p>
              <p className="text-sm text-muted-foreground">P99 Latency</p>
            </div>
            <div>
              <p className="text-2xl font-bold" data-testid="metric-error-rate">
                {(metrics.error_rate * 100).toFixed(1)}%
              </p>
              <p className="text-sm text-muted-foreground">Error Rate</p>
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {isEmpty && (
        <EmptyState
          icon={Activity}
          title="No traces recorded yet"
          message="Run a pipeline to generate traces."
          testId="traces-empty"
        />
      )}

      {/* Trace list — real traces, newest first */}
      {summary && !isEmpty && (
        <div data-testid="traces-list">
          <div className="rounded-lg border bg-card p-6">
            <h3 className="text-sm font-medium text-muted-foreground mb-4">Recent Traces</h3>
            {detailError && (
              <p className="mb-3 text-sm text-destructive" data-testid="trace-detail-error">
                Couldn't load that trace: {detailError}
              </p>
            )}
            <div className="space-y-2">
              {summary.recent_traces.map((trace: RecentTrace) => {
                const isActive =
                  trace.last_activity !== undefined &&
                  loadedAtMs - trace.last_activity * 1000 < ACTIVE_BADGE_WINDOW_MS;
                return (
                  <button
                    key={trace.trace_id}
                    className="flex w-full items-center justify-between gap-3 rounded-md border px-4 py-2 text-left hover:bg-accent transition-colors"
                    data-testid={`trace-item-${trace.trace_id}`}
                    onClick={() => handleTraceClick(trace.trace_id)}
                  >
                    <span className="text-sm font-medium font-mono truncate">{trace.trace_id}</span>
                    <span className="flex items-center gap-2 shrink-0">
                      {trace.models && trace.models.length > 0 && (
                        <span className="text-xs text-muted-foreground font-mono">
                          {trace.models.slice(0, 3).join(", ")}
                        </span>
                      )}
                      <span className="text-xs text-muted-foreground">
                        {trace.span_count} spans · {formatDuration(trace.duration_ms)}
                      </span>
                      {(trace.error_count ?? 0) > 0 && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-destructive/10 text-destructive">
                          {trace.error_count} err
                        </span>
                      )}
                      {isActive && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-success/10 text-success">
                          Active
                        </span>
                      )}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Span detail — shown when a trace is selected */}
      {selectedTrace && (
        <div data-testid="traces-span-detail">
          <SpanDetail spans={selectedTrace.spans} traceId={selectedTrace.trace_id} />
        </div>
      )}
    </div>
  );
}
