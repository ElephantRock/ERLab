import { apiFetchUnchecked } from "./client";
import type { SessionListResponse } from "./types";

/**
 * Fetch the list of unique session IDs with run counts.
 * GET /pipeline/runs/sessions
 */
export function getSessionList(): Promise<SessionListResponse> {
  return apiFetchUnchecked("/pipeline/runs/sessions");
}
