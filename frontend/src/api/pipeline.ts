import { apiFetchUnchecked } from "./client";
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
  return apiFetchUnchecked("/pipeline/run", {
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
  return apiFetchUnchecked(`/pipeline/runs${qs ? `?${qs}` : ""}`);
}

export function getRunDetail(id: number): Promise<PipelineRunDetail> {
  return apiFetchUnchecked(`/pipeline/runs/detail/${id}`);
}

export function cancelRun(runId: string): Promise<{ status: string; run_id: string }> {
  return apiFetchUnchecked(`/pipeline/runs/${runId}`, { method: "DELETE" });
}

export function getRunIdeas(runId: string): Promise<{ ideas: IdeaSummary[]; total: number }> {
  return apiFetchUnchecked(`/pipeline/runs/${runId}/ideas`);
}

export function resumeRun(runId: string): Promise<{ status: string; run_id: string; ideas_count: number; gaps_count: number; proposals_count: number }> {
  return apiFetchUnchecked(`/pipeline/resume/${runId}`, {
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
  return apiFetchUnchecked(`/pipeline/estimate?strategy=${encodeURIComponent(strategy)}`);
}

export function triggerAutonomous(req: AutonomousCycleRequest): Promise<AutonomousCycleResponse> {
  return apiFetchUnchecked("/pipeline/autonomous", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
