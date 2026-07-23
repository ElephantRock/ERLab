import { callContract } from "./contracts/common";
import { listIdeasContract } from "./contracts/dashboard";
import { getSectionRevisionsContract } from "./contracts/f1-3a-reads";
import {
  getIdeaContract,
  refineIdeaContract,
  refineSectionContract,
  restoreSectionContract,
  submitFeedbackContract,
} from "./contracts/ideas";
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
  return callContract(getIdeaContract, { params: { id } });
}

export function submitFeedback(
  id: number,
  req: IdeaFeedbackRequest,
): Promise<{ id: number; user_rating: number; user_notes: string | null }> {
  return callContract(submitFeedbackContract, { params: { id }, body: req });
}

export function refineIdea(
  id: number,
): Promise<{ id: number; novelty_score: number; feasibility_score: number; proposal_title: string }> {
  return callContract(refineIdeaContract, { params: { id } });
}

// --- Section refinement (Release 2) ---

export function refineSection(
  ideaId: number,
  sectionKey: string,
  expectedCurrentHash: string,
  triggerDetail?: Record<string, unknown>,
): Promise<SectionRefinementResponse> {
  return callContract(refineSectionContract, {
    params: { ideaId, sectionKey },
    body: {
      expected_current_hash: expectedCurrentHash,
      trigger_detail: triggerDetail,
    },
  });
}

export function restoreSection(
  ideaId: number,
  sectionKey: string,
  revisionId: number,
  expectedCurrentHash: string,
): Promise<SectionRefinementResponse> {
  return callContract(restoreSectionContract, {
    params: { ideaId, sectionKey, revisionId },
    body: { expected_current_hash: expectedCurrentHash },
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
