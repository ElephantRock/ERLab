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
  session_id?: string;
}): Promise<{ runs: PipelineRunSummary[]; total: number }> {
  const search = new URLSearchParams();
  if (params?.limit) search.set("limit", String(params.limit));
  if (params?.offset) search.set("offset", String(params.offset));
  if (params?.session_id) search.set("session_id", params.session_id);
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

export function resumeRun(runId: string): Promise<{ status: string; run_id: string; ideas_count: number; gaps_count: number; proposals_count: number }> {
  return apiFetch(`/pipeline/resume/${runId}`, {
    method: "POST",
  });
}

export interface EstimateBreakdown {
  stage: string;
  model: string;
  label: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  time_seconds: number;
}

export interface EstimateResponse {
  strategy: string;
  stages: number;
  estimated_cost_usd: number;
  estimated_time_seconds: number;
  estimated_time_display: string;
  cost_display: string;
  local_cost_usd: number;
  cloud_cost_usd: number;
  breakdown: EstimateBreakdown[];
}

export function getEstimate(strategy: string): Promise<EstimateResponse> {
  return apiFetch(`/pipeline/estimate?strategy=${encodeURIComponent(strategy)}`);
}

export function triggerAutonomous(req: AutonomousCycleRequest): Promise<AutonomousCycleResponse> {
  return apiFetch("/pipeline/autonomous", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
