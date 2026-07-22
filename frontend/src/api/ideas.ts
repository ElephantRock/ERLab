import { apiFetchUnchecked } from "./client";
import { callContract } from "./contracts/common";
import { listIdeasContract } from "./contracts/dashboard";
import { getSectionRevisionsContract } from "./contracts/f1-3a-reads";
import type {
  IdeaListResponse,
  IdeaDetail,
  IdeaFeedbackRequest,
  SectionRefinementResponse,
  RevisionHistoryResponse,
} from "./types";

export function listIdeas(params?: {
  domain?: string;
  min_score?: number;
  search?: string;
  sort_by?: string;
  sort_order?: string;
  limit?: number;
  offset?: number;
}): Promise<IdeaListResponse> {
  // F1.3a: migrated from apiFetchUnchecked to callContract with runtime decoder
  return callContract(listIdeasContract, { query: params }) as Promise<IdeaListResponse>;
}

export function getIdea(id: number): Promise<{ idea: IdeaDetail }> {
  return apiFetchUnchecked(`/ideas/${id}`);
}

export function submitFeedback(
  id: number,
  req: IdeaFeedbackRequest,
): Promise<{ id: number; user_rating: number; user_notes: string | null }> {
  return apiFetchUnchecked(`/ideas/${id}/feedback`, {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function refineIdea(
  id: number,
): Promise<{ id: number; novelty_score: number; feasibility_score: number; proposal_title: string }> {
  return apiFetchUnchecked(`/ideas/${id}/refine`, { method: "POST" });
}

// --- Section refinement (Release 2) ---

export function refineSection(
  ideaId: number,
  sectionKey: string,
  expectedCurrentHash: string,
  triggerDetail?: Record<string, unknown>,
): Promise<SectionRefinementResponse> {
  return apiFetchUnchecked(`/ideas/${ideaId}/sections/${sectionKey}/refine`, {
    method: "POST",
    body: JSON.stringify({
      expected_current_hash: expectedCurrentHash,
      trigger_detail: triggerDetail,
    }),
  });
}

export function restoreSection(
  ideaId: number,
  sectionKey: string,
  revisionId: number,
  expectedCurrentHash: string,
): Promise<SectionRefinementResponse> {
  return apiFetchUnchecked(`/ideas/${ideaId}/sections/${sectionKey}/restore/${revisionId}`, {
    method: "POST",
    body: JSON.stringify({ expected_current_hash: expectedCurrentHash }),
  });
}

export function getSectionRevisions(
  ideaId: number,
  sectionKey: string,
): Promise<RevisionHistoryResponse> {
  // F1.3a: migrated from apiFetchUnchecked to callContract with runtime decoder
  return callContract(getSectionRevisionsContract, {
    params: { ideaId, sectionKey },
  });
}
