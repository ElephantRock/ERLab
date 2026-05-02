import { apiFetch } from "./client";
import type {
  PipelineRunRequest,
  PipelineRunSummary,
  PipelineRunDetail,
  TriggerRunResponse,
  AutonomousCycleRequest,
  AutonomousCycleResponse,
  IdeaSummary,
} from "./types";

export function triggerRun(req: PipelineRunRequest): Promise<TriggerRunResponse> {
  return apiFetch("/pipeline/run", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function listRuns(params?: {
  limit?: number;
  offset?: number;
}): Promise<{ runs: PipelineRunSummary[]; total: number }> {
  const search = new URLSearchParams();
  if (params?.limit) search.set("limit", String(params.limit));
  if (params?.offset) search.set("offset", String(params.offset));
  const qs = search.toString();
  return apiFetch(`/pipeline/runs${qs ? `?${qs}` : ""}`);
}

export function getRunDetail(id: number): Promise<PipelineRunDetail> {
  return apiFetch(`/pipeline/runs/detail/${id}`);
}

export function cancelRun(runId: string): Promise<{ status: string; run_id: string }> {
  return apiFetch(`/pipeline/runs/${runId}`, { method: "DELETE" });
}

export function getRunIdeas(runId: number): Promise<{ ideas: IdeaSummary[]; total: number }> {
  return apiFetch(`/pipeline/runs/${runId}/ideas`);
}

export function triggerAutonomous(req: AutonomousCycleRequest): Promise<AutonomousCycleResponse> {
  return apiFetch("/pipeline/autonomous", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
