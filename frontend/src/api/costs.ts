/**
 * Cost API Client — BATCH-18/TASK-01
 *
 * Typed functions for all 5 cost endpoints.
 * Endpoint shapes from backend/api/routes/costs.py:
 *   GET /costs/summary     → {total_cost_usd, total_tokens, event_count}
 *   GET /costs/by-provider → {provider_name: {cost_usd, input_tokens, output_tokens, calls}}
 *   GET /costs/by-stage    → {stage_name: {cost_usd, input_tokens, output_tokens, calls}}
 *   GET /costs/by-model    → {model_name: {cost_usd, input_tokens, output_tokens, calls}}
 *   GET /costs/run/{id}    → {run_id, summary, by_provider, by_stage}
 */

import { apiFetchUnchecked } from "./client";

// ── Types ────────────────────────────────────────────────────────

export interface CostSummary {
  total_cost_usd: number;
  total_tokens: number;
  event_count: number;
}

export interface BreakdownEntry {
  cost_usd: number;
  input_tokens: number;
  output_tokens: number;
  calls: number;
}

/** Dict keyed by provider name */
export type ProviderBreakdown = Record<string, BreakdownEntry>;

/** Dict keyed by stage name */
export type StageBreakdown = Record<string, BreakdownEntry>;

/** Dict keyed by model name */
export type ModelBreakdown = Record<string, BreakdownEntry>;

export interface RunCostBreakdown {
  run_id: string;
  summary: CostSummary;
  by_provider: ProviderBreakdown;
  by_stage: StageBreakdown;
}

// ── API Functions ────────────────────────────────────────────────

export function getCostSummary(): Promise<CostSummary> {
  return apiFetchUnchecked<CostSummary>("/costs/summary");
}

export function getCostByProvider(): Promise<ProviderBreakdown> {
  return apiFetchUnchecked<ProviderBreakdown>("/costs/by-provider");
}

export function getCostByStage(): Promise<StageBreakdown> {
  return apiFetchUnchecked<StageBreakdown>("/costs/by-stage");
}

export function getCostByModel(): Promise<ModelBreakdown> {
  return apiFetchUnchecked<ModelBreakdown>("/costs/by-model");
}

export function getRunCostBreakdown(runId: string): Promise<RunCostBreakdown> {
  return apiFetchUnchecked<RunCostBreakdown>(`/costs/run/${runId}`);
}
