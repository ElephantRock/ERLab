/**
 * F1.1 — Idea/proposal-section decoders (M1 repair).
 *
 * The pre-F1.1 `proposal-review-panel.tsx` cast `raw as EnsembleReview` with
 * only a `typeof === "object"` guard. Any shape mismatch surfaced as a
 * runtime undefined-field error, not a typed failure. This decoder replaces
 * that with runtime validation of the material fields.
 *
 * Used for the `proposal_sections.ensemble_review` sub-field of an idea
 * detail response — NOT a top-level endpoint. It's a value decoder, called
 * by the consumer that already has the parent payload.
 */

import type {
  EnsembleReview,
  IdeaDetail,
  IdeaFeedbackRequest,
  PerspectiveReview,
  SectionRefinementResponse,
} from "@/api/types";
import {
  decodeArray,
  decodeBoolean,
  decodeNumber,
  decodeObject,
  decodeString,
  type JsonContract,
} from "./common";

// A perspective review: material fields are perspective (identity) and
// score (drives display). The three string arrays are validated as
// arrays-of-string when present.
const perspectiveReviewDecoder = decodeObject<PerspectiveReview>({
  required: {
    perspective: decodeString,
    score: decodeNumber,
  },
  optional: {
    strengths: decodeArray(decodeString),
    weaknesses: decodeArray(decodeString),
    suggestions: decodeArray(decodeString),
  },
});

/**
 * Decode an unknown value into a validated EnsembleReview, or return null
 * if the value is absent/malformed in a way that means "no review present"
 * (null/undefined/non-object). A present-but-malformed object (e.g.
 * missing overall_score) throws ApiContractError — the consumer surfaces
 * that as a failed state, NOT an empty review.
 */
export function decodeEnsembleReview(value: unknown): EnsembleReview | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "object" || Array.isArray(value)) return null;
  const decoder = decodeObject<EnsembleReview>({
    required: {
      overall_score: decodeNumber,
      summary: decodeString,
    },
    optional: {
      methodology: perspectiveReviewDecoder,
      novelty: perspectiveReviewDecoder,
      clarity: perspectiveReviewDecoder,
      consensus_strengths: decodeArray(decodeString),
      critical_weaknesses: decodeArray(decodeString),
      actionable_suggestions: decodeArray(decodeString),
      risk_flags: decodeArray(decodeString),
    },
  });
  return decoder.decode(value, { endpointId: "ideas.ensembleReview" });
}

// ── F1.7a — Idea detail / mutation endpoint contracts ───────────────
//
// Backend sources (backend/api/routes/ideas.py):
//   GET  /ideas/{id}                                  → { idea: IdeaDetail }
//   POST /ideas/{id}/feedback                         → { id, user_rating, user_notes }
//   POST /ideas/{id}/refine                           → { id, novelty_score, feasibility_score, proposal_title }
//   POST /ideas/{id}/sections/{key}/refine            → SectionRefinementResponse
//   POST /ideas/{id}/sections/{key}/restore/{rev_id}  → SectionRefinementResponse
//
// IdeaDetail extends IdeaSummary and carries many deeply nested optional
// fields (novelty_report, feasibility_report, proposal_sections,
// proposal_references, supporting_papers, quality_checks, section_hashes,
// remediation_hints, citation_audit, experiment_results, ...). The decoder
// validates the material identity/display fields plus the array structure of
// source_gap_ids; nested report/section blobs are preserved via decodeObject's
// forward-compat spread and consumed opaquely by the proposal-review panel
// (which runs decodeEnsembleReview on the relevant sub-field itself).

const ideaDetailDecoder = decodeObject<IdeaDetail>({
  required: {
    id: decodeNumber,
    title: decodeString,
    domain: decodeString,
    problem_statement: decodeString,
    proposed_method: decodeString,
    expected_contributions: decodeString,
    created_at: decodeString,
  },
  optional: {
    novelty_score: decodeNumber,
    feasibility_score: decodeNumber,
    overall_score: decodeNumber,
    // source_gap_ids is `string[] | null` — validated as a string array when
    // present-and-non-null, preserved as null otherwise.
    source_gap_ids: decodeArray(decodeString),
    proposal_md: decodeString,
    proposal_latex: decodeString,
  },
});

export const getIdeaContract: JsonContract<{ idea: IdeaDetail }> = {
  id: "ideas.getIdea",
  method: "GET",
  pathPattern: "/ideas/{id}",
  responseKind: "json",
  decoder: decodeObject<{ idea: IdeaDetail }>({
    required: { idea: ideaDetailDecoder },
  }),
};

// submitFeedback returns the partial feedback echo (id + rating + notes),
// NOT the full idea. Callers invalidate/refetch the canonical getIdea query
// after a successful mutation; they must not render this as a complete idea.
export const submitFeedbackContract: JsonContract<{
  id: number;
  user_rating: number;
  user_notes: string | null;
}> = {
  id: "ideas.submitFeedback",
  method: "POST",
  pathPattern: "/ideas/{id}/feedback",
  responseKind: "json",
  decoder: decodeObject<{ id: number; user_rating: number; user_notes: string | null }>({
    required: { id: decodeNumber, user_rating: decodeNumber },
    optional: { user_notes: decodeString },
  }),
};

// refineIdea returns the partial score echo (id + scores + title), NOT the
// full idea. Same invalidate-and-refetch contract as submitFeedback.
export const refineIdeaContract: JsonContract<{
  id: number;
  novelty_score: number;
  feasibility_score: number;
  proposal_title: string;
}> = {
  id: "ideas.refineIdea",
  method: "POST",
  pathPattern: "/ideas/{id}/refine",
  responseKind: "json",
  decoder: decodeObject<{
    id: number;
    novelty_score: number;
    feasibility_score: number;
    proposal_title: string;
  }>({
    required: {
      id: decodeNumber,
      novelty_score: decodeNumber,
      feasibility_score: decodeNumber,
      proposal_title: decodeString,
    },
  }),
};

// SectionRefinementResponse is a complete, well-defined mutation result. Its
// material fields (revision_id, section_key, previous_hash, section_hash) are
// validated strictly. The before/after quality-check arrays validate the
// material identity/decision fields (section, label, word counts, passed
// booleans); model_receipt is `object | null` and is preserved via the
// forward-compat spread.
const qualityCheckResultDecoder = decodeObject<{
  section: string;
  label: string;
  present: boolean;
  word_count: number;
  min_words: number;
  meets_word_count: boolean;
  checks: { name: string; passed: boolean }[];
  passed: boolean;
  failures: string[];
}>({
  required: {
    section: decodeString,
    label: decodeString,
    present: decodeBoolean,
    word_count: decodeNumber,
    min_words: decodeNumber,
    meets_word_count: decodeBoolean,
    checks: decodeArray(
      decodeObject<{ name: string; passed: boolean }>({
        required: { name: decodeString, passed: decodeBoolean },
      }),
    ),
    passed: decodeBoolean,
    failures: decodeArray(decodeString),
  },
});

const sectionRefinementDecoder = decodeObject<SectionRefinementResponse>({
  required: {
    revision_id: decodeNumber,
    section_key: decodeString,
    previous_hash: decodeString,
    section_hash: decodeString,
    quality_checks_before: decodeArray(qualityCheckResultDecoder),
    quality_checks_after: decodeArray(qualityCheckResultDecoder),
  },
  // model_receipt is `{...} | null` — validated as a non-null object when
  // present, preserved as null otherwise.
  optional: {
    model_receipt: decodeObject({ required: {} }),
  },
});

export const refineSectionContract: JsonContract<SectionRefinementResponse> = {
  id: "ideas.refineSection",
  method: "POST",
  pathPattern: "/ideas/{ideaId}/sections/{sectionKey}/refine",
  responseKind: "json",
  decoder: sectionRefinementDecoder,
};

export const restoreSectionContract: JsonContract<SectionRefinementResponse> = {
  id: "ideas.restoreSection",
  method: "POST",
  pathPattern: "/ideas/{ideaId}/sections/{sectionKey}/restore/{revisionId}",
  responseKind: "json",
  decoder: sectionRefinementDecoder,
};

// Re-export IdeaFeedbackRequest for clients that construct the request body.
export type { IdeaFeedbackRequest };
