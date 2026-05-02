import { apiFetch } from "./client";
import type { GapListResponse, ResearchGap } from "./types";

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
  return apiFetch(`/gaps/${qs ? `?${qs}` : ""}`);
}

export function getGap(id: number): Promise<{ gap: ResearchGap }> {
  return apiFetch(`/gaps/${id}`);
}

export function submitGapFeedback(gapId: number, rating: number, notes?: string): Promise<{ gap: ResearchGap }> {
  const params = new URLSearchParams({ rating: String(rating) });
  if (notes) params.set("notes", notes);
  return apiFetch(`/gaps/${gapId}/feedback?${params}`, { method: "POST" });
}

export function updateGapStatus(gapId: number, status: string): Promise<{ gap: ResearchGap }> {
  return apiFetch(`/gaps/${gapId}/status?status=${encodeURIComponent(status)}`, { method: "PATCH" });
}
