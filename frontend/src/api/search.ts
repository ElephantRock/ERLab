import { callContract } from "./contracts/common";
import { globalSearchContract } from "./contracts/group3";
import type { GlobalSearchResponse } from "./types";

/**
 * Global search across ideas, gaps, papers, and runs.
 * GET /search/?q=...&types=...
 *
 * F1.7a: migrated from apiFetchUnchecked to callContract with a runtime
 * decoder.
 */
export function globalSearch(
  query: string,
  types?: string[],
): Promise<GlobalSearchResponse> {
  return callContract(globalSearchContract, {
    query: {
      q: query,
      // The backend expects a comma-joined string; pass it through withQuery
      // as a single value (an array would produce repeated keys).
      types: types && types.length > 0 ? types.join(",") : undefined,
    },
  });
}
