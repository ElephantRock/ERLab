/**
 * SpanDetail — BATCH-21/TASK-01
 *
 * Displays the list of spans for a specific trace: name, kind, status,
 * duration, and — when the cost linker stamped them — the serving models,
 * cost, and token count.
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

/** Safe readers for the open span shape — everything but name/duration_ms
 *  is `unknown` by contract and rendered only when well-typed. */
function asStringArray(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}

function asNumber(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function asString(v: unknown): string | null {
  return typeof v === "string" && v ? v : null;
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
        {spans.map((span, idx) => {
          const kind = asString(span.kind);
          const status = asString(span.status);
          const models = asStringArray(
            span.attributes && typeof span.attributes === "object"
              ? (span.attributes as Record<string, unknown>).models
              : undefined,
          );
          const cost = asNumber(span.cost_usd);
          const tokens = asNumber(span.token_count);
          const isError = status === "error";
          return (
            <div
              key={`${span.name}-${idx}`}
              className={`flex items-center justify-between gap-3 rounded-md border px-4 py-2${
                isError ? " border-destructive/40 bg-destructive/5" : ""
              }`}
              data-testid={`span-row-${idx}`}
            >
              <span className="min-w-0">
                <span className="text-sm font-medium mr-2" data-testid={`span-name-${idx}`}>
                  {span.name}
                </span>
                {kind && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground mr-1">
                    {kind}
                  </span>
                )}
                {models.length > 0 && (
                  <span
                    className="text-xs font-mono text-muted-foreground"
                    data-testid={`span-models-${idx}`}
                  >
                    {models.join(", ")}
                  </span>
                )}
              </span>
              <span className="flex items-center gap-2 shrink-0">
                {isError && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-destructive/10 text-destructive">
                    error
                  </span>
                )}
                {cost !== null && cost > 0 && (
                  <span className="text-xs text-muted-foreground">${cost.toFixed(4)}</span>
                )}
                {tokens !== null && tokens > 0 && (
                  <span className="text-xs text-muted-foreground">{tokens.toLocaleString()} tok</span>
                )}
                <span className="text-sm text-muted-foreground" data-testid={`span-duration-${idx}`}>
                  {formatDuration(span.duration_ms)}
                </span>
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
