import { useState, useEffect, useRef } from "react";
import { apiFetch } from "@/api/client";
import { PIPELINE_STAGES } from "@/lib/constants";

export interface StageProgress {
  key: string;
  label: string;
  status: "pending" | "running" | "completed";
  elapsed: number;
}

interface RunDetail {
  id: number;
  status: string;
  current_stage: string | null;
  stages_completed: string[];
  created_at: string;
  completed_at: string | null;
}

/**
 * usePipelineProgress — tracks pipeline stage progress via REST polling.
 *
 * Previously used SSE (Server-Sent Events) but the Vite dev proxy doesn't
 * reliably stream SSE responses. Polling the run detail endpoint every 2s
 * is simpler, more reliable, and works through any proxy.
 *
 * The run-detail page already uses TanStack Query with refetchInterval=3000
 * for the same purpose. This hook serves the pipeline-new page.
 */
export function usePipelineProgress(runId: string | null) {
  const [stages, setStages] = useState<StageProgress[]>(
    PIPELINE_STAGES.map((s) => ({ key: s.key, label: s.label, status: "pending" as const, elapsed: 0 })),
  );
  const [isComplete, setIsComplete] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const startTimeRef = useRef<number | null>(null);

  // Initialize start time when runId first appears
  useEffect(() => {
    if (runId && !startTimeRef.current) {
      startTimeRef.current = Date.now();
      setIsConnected(true);
      setError(null);
    }
    if (!runId) {
      startTimeRef.current = null;
      setIsConnected(false);
      setIsComplete(false);
      setError(null);
      setStages(PIPELINE_STAGES.map((s) => ({ key: s.key, label: s.label, status: "pending" as const, elapsed: 0 })));
    }
  }, [runId]);

  // Poll run detail endpoint every 2 seconds
  useEffect(() => {
    if (!runId) return;

    let cancelled = false;
    let timeout: ReturnType<typeof setTimeout>;

    async function poll() {
      if (cancelled) return;
      try {
        // Try UUID-based detail endpoint first, then numeric
        let data: RunDetail | null = null;
        try {
          data = await apiFetch<RunDetail>(`/pipeline/runs/detail/${runId}`);
        } catch {
          // Fallback: try listing recent runs
          try {
            const list = await apiFetch<{ runs: RunDetail[] }>(`/pipeline/runs?limit=5`);
            data = list.runs.find((r: RunDetail) => String(r.id) === runId) ?? null;
          } catch {
            // Both failed
          }
        }

        if (cancelled || !data) return;

        setIsConnected(true);

        // Update stages based on current_stage and stages_completed
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

        // Check completion
        if (data.status === "completed" || data.status === "failed") {
          setIsComplete(true);
          setIsConnected(false);
          // Mark all stages as completed on finish
          if (data.status === "completed") {
            setStages((prev) =>
              prev.map((s) =>
                s.status !== "completed" ? { ...s, status: "completed" as const } : s
              ),
            );
          }
          return; // Stop polling
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to fetch progress");
        }
      }

      // Schedule next poll
      if (!cancelled) {
        timeout = setTimeout(poll, 2000);
      }
    }

    // Start polling immediately
    poll();

    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [runId]);

  const currentStage = stages.find((s) => s.status === "running")?.label ?? null;

  return { stages, currentStage, isComplete, isConnected, error };
}
