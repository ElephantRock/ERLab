import { callContract } from "./contracts/common";
import { listRunsContract } from "./contracts/dashboard";
import {
  cancelRunContract,
  getEstimateContract,
  getRunDetailContract,
  getRunIdeasContract,
  resumeRunContract,
  triggerAutonomousContract,
  triggerRunContract,
} from "./contracts/pipeline";
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
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder.
  // The 202 response includes a preflight sub-object (can_proceed + warnings).
  return callContract(triggerRunContract, { body: req });
}

export function listRuns(params?: {
  limit?: number;
  offset?: number;
  session_id?: string;
}): Promise<{ runs: PipelineRunSummary[]; total: number }> {
  // F1.3a: migrated from apiFetchUnchecked to callContract with runtime decoder
  return callContract(listRunsContract, { query: params });
}

export function getRunDetail(id: number): Promise<PipelineRunDetail> {
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder.
  return callContract(getRunDetailContract, { params: { id } });
}

export function cancelRun(runId: string): Promise<{ status: string; run_id: string }> {
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder.
  return callContract(cancelRunContract, { params: { runId } });
}

export function getRunIdeas(runId: string): Promise<{ ideas: IdeaSummary[]; total: number }> {
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder.
  return callContract(getRunIdeasContract, { params: { runId } });
}

export function resumeRun(runId: string): Promise<{ status: string; run_id: string; ideas_count: number; gaps_count: number; proposals_count: number }> {
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder.
  return callContract(resumeRunContract, { params: { runId } });
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

export function getEstimate(strategy: string, experimentSpecId?: string | null): Promise<EstimateResponse> {
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder.
  return callContract(getEstimateContract, {
    query: {
      strategy,
      experiment_spec_id: experimentSpecId || undefined,
    },
  });
}

export function triggerAutonomous(req: AutonomousCycleRequest): Promise<AutonomousCycleResponse> {
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder.
  return callContract(triggerAutonomousContract, { body: req });
}
