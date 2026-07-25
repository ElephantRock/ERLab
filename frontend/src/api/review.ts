/**
 * Phase 2 2B/2E: Trust & Sources review API client.
 *
 * Calls the normalized review endpoints under /ideas/{id}/review/*.
 */
import {
  callContract,
  decodeArray,
  decodeBoolean,
  decodeObject,
  decodeNumber,
  decodeString,
  type JsonContract,
  type ResponseDecoder,
} from "./contracts/common";
import type {
  ReviewAutomatedChecks,
  ReviewSource,
  ReviewPayload,
  HumanReviewSummary,
  SourceReviewDecisionRequest,
} from "./types";

// ── Decoders ────────────────────────────────────────────────────────
// Validate the top-level + first-level structure so a malformed backend
// response surfaces as a contract failure. Deeply-optional nested fields
// (e.g. per-dimension score dicts) are read defensively by the UI, so the
// decoders validate only the material identity fields and pass the rest
// through via decodeObject's forward-compatibility (unknown extra fields
// preserved).

const automatedChecksDecoder: ResponseDecoder<ReviewAutomatedChecks> = decodeObject<ReviewAutomatedChecks>({
  required: {
    paper_evaluation: dec<ReviewAutomatedChecks["paper_evaluation"]>((v) =>
      v && typeof v === "object" ? (v as ReviewAutomatedChecks["paper_evaluation"]) : ({ status: "unavailable", scope: "paper" }),
    ),
    proposal_evaluation: dec<ReviewAutomatedChecks["proposal_evaluation"]>((v) =>
      v && typeof v === "object" ? (v as ReviewAutomatedChecks["proposal_evaluation"]) : null,
    ),
    citation_audit: dec<ReviewAutomatedChecks["citation_audit"]>((v) =>
      Array.isArray(v) ? (v as ReviewAutomatedChecks["citation_audit"]) : [],
    ),
    quality_checks: dec<ReviewAutomatedChecks["quality_checks"]>((v) =>
      Array.isArray(v) ? (v as ReviewAutomatedChecks["quality_checks"]) : [],
    ),
  },
});

// Helper to wrap a plain coercion into a ResponseDecoder object.
function dec<T>(fn: (value: unknown) => T): ResponseDecoder<T> {
  return { decode: (value) => fn(value) };
}

const nullableString = dec<string | null>((v) => (v == null ? null : String(v)));
const nullableNumber = dec<number | null>((v) => (typeof v === "number" ? v : null));

const sourceDecoder: ResponseDecoder<ReviewSource> = decodeObject<ReviewSource>({
  required: {
    source_ref_hash: decodeString,
    citation_marker: nullableString,
    ref_number: nullableNumber,
    raw: decodeString,
    title: nullableString,
    authors: nullableString,
    year: nullableString,
    venue: nullableString,
    url: nullableString,
    doi: nullableString,
    resolution_status: dec((v) => (v === "resolved" ? "resolved" : "unresolved") as "resolved" | "unresolved"),
    match_method: nullableString,
    confidence: nullableNumber,
    sections_used: dec<string[]>((v) => (Array.isArray(v) ? (v as string[]) : [])),
    human_decision: dec<ReviewSource["human_decision"]>((v) =>
      v && typeof v === "object" ? (v as ReviewSource["human_decision"]) : null,
    ),
  },
});

const humanReviewDecoder: ResponseDecoder<HumanReviewSummary> = decodeObject<HumanReviewSummary>({
  required: {
    status: dec<HumanReviewSummary["status"]>((v) => {
      const s = String(v);
      return ["not_started", "in_progress", "completed", "completed_with_flags"].includes(s)
        ? (s as HumanReviewSummary["status"])
        : "not_started";
    }),
    reviewable_sources: decodeNumber,
    reviewed_sources: decodeNumber,
    accepted: decodeNumber,
    flagged_or_excluded: decodeNumber,
    decisions_total: decodeNumber,
  },
});

const reviewDecoder: ResponseDecoder<ReviewPayload> = decodeObject<ReviewPayload>({
  required: {
    idea_id: decodeNumber,
    automated_checks: automatedChecksDecoder,
    sources: decodeArray(sourceDecoder),
    human_review: humanReviewDecoder,
    regeneration_available: decodeBoolean,
  },
});

const sourceDecisionDecoder = decodeObject<{ id: number; idea_id: number; decision: string }>({
  required: {
    id: decodeNumber,
    idea_id: decodeNumber,
    decision: decodeString,
  },
});

// ── Contracts ───────────────────────────────────────────────────────

export const getReviewContract: JsonContract<ReviewPayload> = {
  id: "review.getReview",
  method: "GET",
  pathPattern: "/ideas/{idea_id}/review",
  responseKind: "json",
  decoder: reviewDecoder,
};

export const recordSourceDecisionContract: JsonContract<{ id: number; idea_id: number; decision: string }> = {
  id: "review.recordSourceDecision",
  method: "POST",
  pathPattern: "/ideas/{idea_id}/review/sources/decisions",
  responseKind: "json",
  decoder: sourceDecisionDecoder,
};

// ── Client functions ────────────────────────────────────────────────

/** GET /ideas/{id}/review — normalized trust & sources payload. */
export function getReview(ideaId: number): Promise<ReviewPayload> {
  return callContract(getReviewContract, { params: { idea_id: ideaId } });
}

/** POST /ideas/{id}/review/sources/decisions — record a source-review decision. */
export function recordSourceDecision(
  ideaId: number,
  req: SourceReviewDecisionRequest,
): Promise<{ id: number; idea_id: number; decision: string }> {
  return callContract(recordSourceDecisionContract, { params: { idea_id: ideaId }, body: req });
}
