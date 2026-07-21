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
 * listGaps remains on the pre-contract apiFetchUnchecked path for now (it's a
 * lower-risk read; migration tracks under the F1.1 scope-controlled
 * ratchet). It will move to the contract layer when its decoder is added.
 */

import { apiFetchUnchecked } from "./client";
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
  const search = new URLSearchParams();
  if (params?.run_id) search.set("run_id", String(params.run_id));
  if (params?.limit) search.set("limit", String(params.limit));
  if (params?.offset) search.set("offset", String(params.offset));
  if (params?.search) search.set("search", params.search);
  if (params?.gap_type) search.set("gap_type", params.gap_type);
  if (params?.min_confidence !== undefined && params.min_confidence > 0)
    search.set("min_confidence", String(params.min_confidence));
  if (params?.sort_by) search.set("sort_by", params.sort_by);
  if (params?.sort_order) search.set("sort_order", params.sort_order);
  const qs = search.toString();
  return apiFetchUnchecked(`/gaps/${qs ? `?${qs}` : ""}`);
}

export const getGap = getGapViaContract;

export const submitGapFeedback = submitGapFeedbackViaContract;

export const updateGapStatus = updateGapStatusViaContract;

// Re-export GapStatus as a value namespace for runtime narrowing helpers.
export const GAP_STATUSES: readonly GapStatus[] = ["identified", "investigating", "addressed"] as const;

/** Narrow an unknown string to GapStatus; returns null if invalid. */
export function asGapStatus(value: string): GapStatus | null {
  return (GAP_STATUSES as readonly string[]).includes(value) ? (value as GapStatus) : null;
}
