/**
 * Gaps API — F1.1 canonical boundary.
 *
 * getGap, submitGapFeedback, and updateGapStatus are now routed through the
 * contract layer (clients/gaps-client.ts + contracts/gaps.ts) with runtime
 * response decoders. The mutation functions return TRUTHFUL partial result
 * types (GapFeedbackMutationResult / GapStatusMutationResult), NOT the full
 * ResearchGap — see contracts/gaps.ts for why (the backend returns only
 * {id, user_rating, user_notes} / {id, status}).
 *
 * listGaps is migrated to the contract layer under F1.7a — its decoder
 * reuses researchGapDecoder so the list path gets the same field-level
 * validation as the detail path.
 */

import { callContract } from "./contracts/common";
import { listGapsContract } from "./contracts/gaps";
import { getGapClustersContract, type GapClustersResponse } from "./contracts/f1-3a-reads";
import type { GapListResponse } from "./types";
import {
  getGap as getGapViaContract,
  submitGapFeedback as submitGapFeedbackViaContract,
  updateGapStatus as updateGapStatusViaContract,
  type GapStatus,
} from "./clients/gaps-client";

// Re-export the truthful mutation result types + GapStatus so consumers
// can type their handlers without a second import path.
export type {
  GapFeedbackMutationResult,
  GapStatusMutationResult,
  GapStatus,
} from "./clients/gaps-client";

export function listGaps(params?: {
  run_id?: number;
  limit?: number;
  offset?: number;
  search?: string;
  gap_type?: string;
  min_confidence?: number;
  sort_by?: string;
  sort_order?: string;
}): Promise<GapListResponse> {
  // callContract's withQuery drops undefined/null/empty values. run_id and
  // min_confidence are only sent when truthy/positive to preserve the
  // pre-migration query behavior (a zero run_id/min_confidence would
  // otherwise broaden the filter).
  const query: Record<string, unknown> = {};
  if (params?.run_id) query.run_id = params.run_id;
  if (params?.limit) query.limit = params.limit;
  if (params?.offset) query.offset = params.offset;
  if (params?.search) query.search = params.search;
  if (params?.gap_type) query.gap_type = params.gap_type;
  if (params?.min_confidence !== undefined && params.min_confidence > 0)
    query.min_confidence = params.min_confidence;
  if (params?.sort_by) query.sort_by = params.sort_by;
  if (params?.sort_order) query.sort_order = params.sort_order;
  return callContract(listGapsContract, { query });
}

export const getGap = getGapViaContract;

export const submitGapFeedback = submitGapFeedbackViaContract;

export const updateGapStatus = updateGapStatusViaContract;

/**
 * Fetch gap clusters for the clusters view. F1.3a: migrated from an inline
 * apiFetchUnchecked call in gaps-explorer.tsx to a typed client function
 * with a runtime decoder. Each cluster is preserved as a structured object
 * (the page renders it opaquely via ClusterScatterPlot).
 */
export function getGapClusters(): Promise<GapClustersResponse> {
  return callContract(getGapClustersContract);
}

// Re-export GapStatus as a value namespace for runtime narrowing helpers.
export const GAP_STATUSES: readonly GapStatus[] = ["identified", "investigating", "addressed"] as const;

/** Narrow an unknown string to GapStatus; returns null if invalid. */
export function asGapStatus(value: string): GapStatus | null {
  return (GAP_STATUSES as readonly string[]).includes(value) ? (value as GapStatus) : null;
}
