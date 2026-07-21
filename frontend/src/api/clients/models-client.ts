/**
 * F1.1 — Typed client for the stage-model endpoint contracts (H1 repair).
 *
 * Replaces the three raw `fetch()` calls in stage-model-selector.tsx with
 * canonical `apiFetchUnchecked`-transported, decoder-validated operations. Auth
 * headers (X-API-Key / JWT) are now injected by apiFetchUnchecked's
 * buildAuthHeaders, and failures normalize through ApiError / ApiContractError.
 */

import { callContract } from "@/api/contracts/common";
import {
  getStageModelConfigContract,
  resetStageModelConfigContract,
  updateStageModelConfigContract,
  type StageModelConfig,
  type StageModelResetResult,
  type StageModelStageInfo,
  type StageModelOption,
  type StageModelUpdateResult,
} from "@/api/contracts/models";

// Re-export the domain types so consumers have one import path.
export type {
  StageModelConfig,
  StageModelStageInfo,
  StageModelOption,
  StageModelResetResult,
  StageModelUpdateResult,
};

export function getStageModelConfig(): Promise<StageModelConfig> {
  return callContract(getStageModelConfigContract);
}

export function updateStageModelConfig(
  assignments: Record<string, string>,
): Promise<StageModelUpdateResult> {
  return callContract(updateStageModelConfigContract, { body: assignments });
}

export function resetStageModelConfig(): Promise<StageModelResetResult> {
  return callContract(resetStageModelConfigContract);
}
