/**
 * SpanDetail — BATCH-21/TASK-01
 *
 * Displays the list of spans for a specific trace.
 */

import type { TraceSpan } from "@/api/traces";

interface SpanDetailProps {
  spans: TraceSpan[];
  traceId: string;
}

function formatDuration(ms: number): string {
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(2)}s`;
  }
  return `${ms.toFixed(0)}ms`;
}

export function SpanDetail({ spans, traceId }: SpanDetailProps) {
  return (
    <div className="rounded-lg border bg-card p-6 space-y-4" data-testid="span-detail">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">
          Trace Spans
        </h3>
        <span className="text-xs font-mono text-muted-foreground" data-testid="span-trace-id">
          {traceId}
        </span>
      </div>
      <div className="space-y-2">
        {spans.map((span, idx) => (
          <div
            key={`${span.name}-${idx}`}
            className="flex items-center justify-between rounded-md border px-4 py-2"
            data-testid={`span-row-${idx}`}
          >
            <span className="text-sm font-medium" data-testid={`span-name-${idx}`}>
              {span.name}
            </span>
            <span className="text-sm text-muted-foreground" data-testid={`span-duration-${idx}`}>
              {formatDuration(span.duration_ms)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
