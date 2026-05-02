import { apiFetch } from "./client";

// --- Types ---

export interface CommentItem {
  id: number;
  idea_id: number;
  author: string;
  content: string;
  parent_id: number | null;
  created_at: string;
}

export interface CommentListResponse {
  comments: CommentItem[];
  total: number;
}

export interface CommentCreateRequest {
  author?: string;
  content: string;
  parent_id?: number | null;
}

export interface ShareLinkResponse {
  id: number;
  idea_id: number;
  token: string;
  share_url: string;
  created_at: string;
}

export interface SharedIdeaResponse {
  idea: {
    id: number;
    title: string;
    problem_statement: string;
    proposed_method: string;
    expected_contributions: string;
    domain: string;
    novelty_score: number | null;
    feasibility_score: number | null;
    overall_score: number | null;
    source_gap_ids: string[] | null;
    created_at: string;
  };
}

// --- API Functions ---

export function listComments(ideaId: number): Promise<CommentListResponse> {
  return apiFetch(`/ideas/${ideaId}/comments`);
}

export function addComment(
  ideaId: number,
  req: CommentCreateRequest,
): Promise<CommentItem> {
  return apiFetch(`/ideas/${ideaId}/comments`, {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function createShareLink(ideaId: number): Promise<ShareLinkResponse> {
  return apiFetch(`/ideas/${ideaId}/share`, { method: "POST" });
}

export function getSharedIdea(token: string): Promise<SharedIdeaResponse> {
  return apiFetch(`/shared/${token}`);
}
