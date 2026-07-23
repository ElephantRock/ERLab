import { callContract } from "./contracts/common";
import { getSessionListContract } from "./contracts/group3";
import type { SessionListResponse } from "./types";

/**
 * Fetch the list of unique session IDs with run counts.
 * GET /pipeline/runs/sessions
 *
 * F1.7a: migrated from apiFetchUnchecked to callContract with a runtime
 * decoder.
 */
export function getSessionList(): Promise<SessionListResponse> {
  return callContract(getSessionListContract);
}
