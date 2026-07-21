/**
 * F1.1 — Typed clients for the gaps endpoint contracts.
 *
 * These wrap the contracts in `contracts/gaps.ts` with ergonomic call
 * signatures. The mutation clients (submitGapFeedback, updateGapStatus)
 * return the TRUTHFUL partial result types — NOT the full ResearchGap.
 * Callers must invalidate/refetch the canonical getGap/listGaps query
 * after a successful mutation; they must not render the partial mutation
 * response as a complete gap.
 */

import { callContract } from "@/api/contracts/common";
import {
  getGapContract,
  submitGapFeedbackContract,
  updateGapStatusContract,
  type GapFeedbackMutationResult,
  type GapStatus,
  type GapStatusMutationResult,
} from "@/api/contracts/gaps";
import type { ResearchGap } from "@/api/types";

// Re-export the truthful mutation result types + GapStatus so consumers
// have one import path through api/gaps.ts.
export type { GapFeedbackMutationResult, GapStatusMutationResult, GapStatus };

export function getGap(id: number): Promise<{ gap: ResearchGap }> {
  return callContract(getGapContract, { params: { id } });
}

export function submitGapFeedback(
  gapId: number,
  rating: number,
  notes?: string,
): Promise<{ gap: GapFeedbackMutationResult }> {
  return callContract(submitGapFeedbackContract, {
    params: { gapId },
    query: { rating, notes },
  });
}

export function updateGapStatus(
  gapId: number,
  status: GapStatus,
): Promise<{ gap: GapStatusMutationResult }> {
  return callContract(updateGapStatusContract, {
    params: { gapId },
    query: { status },
  });
}
