import { callContract } from "./contracts/common";
import {
  addCommentContract,
  createShareLinkContract,
  getSharedIdeaContract,
} from "./contracts/collaboration";
import { listCommentsContract } from "./contracts/f1-3a-reads";

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
  // F1.3a: migrated from apiFetchUnchecked to callContract with runtime decoder
  return callContract(listCommentsContract, { params: { ideaId } });
}

export function addComment(
  ideaId: number,
  req: CommentCreateRequest,
): Promise<CommentItem> {
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder.
  return callContract(addCommentContract, { params: { ideaId }, body: req });
}

export function createShareLink(ideaId: number): Promise<ShareLinkResponse> {
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder.
  return callContract(createShareLinkContract, { params: { ideaId } });
}

export function getSharedIdea(token: string): Promise<SharedIdeaResponse> {
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder.
  return callContract(getSharedIdeaContract, { params: { token } });
}
