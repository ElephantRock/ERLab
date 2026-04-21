import { apiFetch } from "./client";
import type { IdeaListResponse, IdeaDetail, IdeaFeedbackRequest } from "./types";

export function listIdeas(params?: {
  domain?: string;
  min_score?: number;
  limit?: number;
  offset?: number;
}): Promise<IdeaListResponse> {
  const search = new URLSearchParams();
  if (params?.domain) search.set("domain", params.domain);
  if (params?.min_score !== undefined) search.set("min_score", String(params.min_score));
  if (params?.limit) search.set("limit", String(params.limit));
  if (params?.offset) search.set("offset", String(params.offset));
  const qs = search.toString();
  return apiFetch(`/ideas/${qs ? `?${qs}` : ""}`);
}

export function getIdea(id: number): Promise<{ idea: IdeaDetail }> {
  return apiFetch(`/ideas/${id}`);
}

export function submitFeedback(
  id: number,
  req: IdeaFeedbackRequest,
): Promise<{ id: number; user_rating: number; user_notes: string | null }> {
  return apiFetch(`/ideas/${id}/feedback`, {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function refineIdea(
  id: number,
): Promise<{ id: number; novelty_score: number; feasibility_score: number; proposal_title: string }> {
  return apiFetch(`/ideas/${id}/refine`, { method: "POST" });
}
