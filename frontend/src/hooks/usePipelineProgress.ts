import { useState, useCallback } from "react";
import { useSSE, isStageProgress, isDone } from "./useSSE";
import { PIPELINE_STAGES } from "@/lib/constants";

export interface StageProgress {
  key: string;
  label: string;
  status: "pending" | "running" | "completed";
  elapsed: number;
}

export function usePipelineProgress(runId: string | null) {
  const [stages, setStages] = useState<StageProgress[]>(
    PIPELINE_STAGES.map((s) => ({ key: s.key, label: s.label, status: "pending" as const, elapsed: 0 })),
  );
  const [isComplete, setIsComplete] = useState(false);

  const handleEvent = useCallback(
    (data: unknown) => {
      if (isDone(data)) {
        setIsComplete(true);
        setStages((prev) =>
          prev.map((s) => (s.status === "running" ? { ...s, status: "completed" as const } : s)),
        );
        return;
      }

      if (isStageProgress(data)) {
        setStages((prev) =>
          prev.map((s) => {
            if (s.key === data.stage) {
              return { ...s, status: "running" as const, elapsed: data.elapsed };
            }
            // Mark previous stages as completed
            const stageIndex = PIPELINE_STAGES.findIndex((p) => p.key === data.stage);
            const currentIndex = PIPELINE_STAGES.findIndex((p) => p.key === s.key);
            if (currentIndex < stageIndex && s.status !== "completed") {
              return { ...s, status: "completed" as const };
            }
            return s;
          }),
        );
      }
    },
    [],
  );

  const path = runId ? `/pipeline/runs/${runId}/progress` : null;
  const { isConnected, error } = useSSE(path!, {
    onEvent: handleEvent,
    enabled: !!runId,
  });

  const currentStage = stages.find((s) => s.status === "running")?.label ?? null;

  return { stages, currentStage, isComplete, isConnected, error };
}
