import { apiFetch } from "./client";
import type { GapListResponse, ResearchGap } from "./types";

export function listGaps(params?: {
  run_id?: number;
  limit?: number;
  offset?: number;
}): Promise<GapListResponse> {
  const search = new URLSearchParams();
  if (params?.run_id) search.set("run_id", String(params.run_id));
  if (params?.limit) search.set("limit", String(params.limit));
  if (params?.offset) search.set("offset", String(params.offset));
  const qs = search.toString();
  return apiFetch(`/gaps/${qs ? `?${qs}` : ""}`);
}

export function getGap(id: number): Promise<{ gap: ResearchGap }> {
  return apiFetch(`/gaps/${id}`);
}
