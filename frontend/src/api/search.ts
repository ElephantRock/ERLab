import { apiFetchUnchecked } from "./client";
import type { GlobalSearchResponse } from "./types";

export function globalSearch(
  query: string,
  types?: string[],
): Promise<GlobalSearchResponse> {
  const params = new URLSearchParams({ q: query });
  if (types && types.length > 0) {
    params.set("types", types.join(","));
  }
  return apiFetchUnchecked(`/search/?${params.toString()}`);
}
