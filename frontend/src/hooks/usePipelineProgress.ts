import { useState, useEffect, useRef, useCallback } from "react";
import { apiFetchUnchecked, sseFetch } from "@/api/client";
import { PIPELINE_STAGES } from "@/lib/constants";
import type { PipelineRunDetail, PipelineRunSummary } from "@/api/types";

export interface StageProgress {
  key: string;
  label: string;
  status: "pending" | "running" | "completed";
  elapsed: number;
}

// F1.1 M6: previously this hook declared a local `RunDetail` interface
// that duplicated a subset of PipelineRunDetail. Now uses the canonical
// type from api/types.ts — the backend returns the full shape at
// /pipeline/runs/detail/{id} and /pipeline/runs, so the wider type is
// truthful (the hook only reads a subset of the fields).

/**
 * usePipelineProgress — tracks pipeline stage progress.
 *
 * Phase 6: Uses SSE with Last-Event-ID replay when available, with REST
 * polling fallback. The SSE transport enables durable reconnect: if the
 * connection drops, we resume from the last received event ID.
 *
 * The REST poll fallback ensures the hook works through any proxy and
 * covers runs that predate the SSE endpoint.
 */
export function usePipelineProgress(runId: string | null) {
  const [stages, setStages] = useState<StageProgress[]>(
    PIPELINE_STAGES.map((s) => ({ key: s.key, label: s.label, status: "pending" as const, elapsed: 0 })),
  );
  const [isComplete, setIsComplete] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const lastEventIdRef = useRef<string | undefined>(undefined);
  const sseControllerRef = useRef<AbortController | null>(null);
  const cancelledRef = useRef(false);

  // Reset state when runId changes
  useEffect(() => {
    if (runId && !startTimeRef.current) {
      startTimeRef.current = Date.now();
      setError(null);
    }
    if (!runId) {
      startTimeRef.current = null;
      lastEventIdRef.current = undefined;
      setIsConnected(false);
      setIsComplete(false);
      setError(null);
      setStages(PIPELINE_STAGES.map((s) => ({ key: s.key, label: s.label, status: "pending" as const, elapsed: 0 })));
    }
    cancelledRef.current = false;
  }, [runId]);

  // ── SSE connection with Last-Event-ID replay ───────────────
  const connectSSE = useCallback(() => {
    if (!runId || cancelledRef.current) return;

    // Clean up any existing connection
    sseControllerRef.current?.abort();

    const controller = sseFetch(
      `/pipeline/runs/${runId}/progress`,
      {
        onEvent: (data: string) => {
          try {
            const evt = JSON.parse(data);
            // Handle progress events
            if (evt.type === "progress" || evt.stage || evt.current_stage) {
              const completedKeys = new Set(evt.stages_completed || []);
              const currentKey = evt.current_stage || evt.stage;
              setStages((prev) =>
                prev.map((s) => {
                  const elapsed = startTimeRef.current
                    ? (Date.now() - startTimeRef.current) / 1000
                    : 0;
                  if (completedKeys.has(s.key)) {
                    return { ...s, status: "completed" as const, elapsed };
                  }
                  if (s.key === currentKey) {
                    return { ...s, status: "running" as const, elapsed };
                  }
                  return s;
                }),
              );
            }
            // Handle completion
            if (evt.type === "complete" || evt.status === "completed" || evt.status === "failed") {
              if (evt.status === "completed" || evt.type === "complete") {
                setStages((prev) =>
                  prev.map((s) =>
                    s.status !== "completed" ? { ...s, status: "completed" as const } : s
                  ),
                );
              }
              setIsComplete(true);
              setIsConnected(false);
            }
          } catch {
            // Non-JSON SSE data — ignore
          }
        },
        onEventId: (id: string) => {
          lastEventIdRef.current = id;
        },
        onOpen: () => {
          setIsConnected(true);
          setError(null);
        },
        onError: (_err: Error) => {
          // SSE failed — fall back to polling
          if (!cancelledRef.current) {
            setIsConnected(false);
            // Don't set error if it's just a connection issue — poll will retry
          }
        },
        shouldReconnect: () => {
          return !cancelledRef.current;
        },
      },
      { lastEventId: lastEventIdRef.current },
    );
    sseControllerRef.current = controller;
  }, [runId]);

  // ── REST polling fallback ──────────────────────────────────
  const pollOnce = useCallback(async (): Promise<boolean> => {
    if (!runId || cancelledRef.current) return false;
    try {
      let data: PipelineRunDetail | null = null;
      try {
        data = await apiFetchUnchecked<PipelineRunDetail>(`/pipeline/runs/detail/${runId}`);
      } catch {
        try {
          const list = await apiFetchUnchecked<{ runs: PipelineRunSummary[]; total: number }>(`/pipeline/runs?limit=5`);
          data = (list.runs.find((r) => String(r.id) === runId) as PipelineRunDetail | undefined) ?? null;
        } catch {
          // Both failed
        }
      }

      if (cancelledRef.current || !data) return false;

      setIsConnected(true);

      const completedKeys = new Set(data.stages_completed || []);
      const currentKey = data.current_stage;

      setStages((prev) =>
        prev.map((s) => {
          const elapsed = startTimeRef.current
            ? (Date.now() - startTimeRef.current) / 1000
            : 0;
          if (completedKeys.has(s.key)) {
            return { ...s, status: "completed" as const, elapsed };
          }
          if (s.key === currentKey) {
            return { ...s, status: "running" as const, elapsed };
          }
          return s;
        }),
      );

      if (data.status === "completed" || data.status === "failed") {
        setIsComplete(true);
        setIsConnected(false);
        if (data.status === "completed") {
          setStages((prev) =>
            prev.map((s) =>
              s.status !== "completed" ? { ...s, status: "completed" as const } : s
            ),
          );
        }
        return false; // Stop polling
      }
      return true; // Continue polling
    } catch (err) {
      if (!cancelledRef.current) {
        setError(err instanceof Error ? err.message : "Failed to fetch progress");
      }
      return true; // Continue polling on error
    }
  }, [runId]);

  // ── Combined SSE + poll effect ─────────────────────────────
  useEffect(() => {
    if (!runId) return;
    cancelledRef.current = false;

    // Try SSE first
    connectSSE();

    // Polling fallback: every 3s for resilience
    let pollTimeout: ReturnType<typeof setTimeout>;
    let stopPolling = false;

    async function pollLoop() {
      while (!stopPolling && !cancelledRef.current) {
        await new Promise<void>((resolve) => {
          pollTimeout = setTimeout(resolve, 3000);
        });
        if (stopPolling || cancelledRef.current) break;
        const shouldContinue = await pollOnce();
        if (!shouldContinue) break;
      }
    }

    pollLoop();

    return () => {
      stopPolling = true;
      cancelledRef.current = true;
      clearTimeout(pollTimeout);
      sseControllerRef.current?.abort();
      sseControllerRef.current = null;
    };
  }, [runId, connectSSE, pollOnce]);

  const currentStage = stages.find((s) => s.status === "running")?.label ?? null;

  return { stages, currentStage, isComplete, isConnected, error };
}
