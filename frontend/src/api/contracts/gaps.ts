/**
 * F1.1 — Gaps endpoint contracts (H3 repair).
 *
 * The gap mutation endpoints (submitGapFeedback, updateGapStatus) return
 * ONLY a partial shape — NOT the full ResearchGap. The pre-F1.1 client
 * type claimed `{ gap: ResearchGap }` (14 fields), causing consumers to
 * read absent fields (title, confidence, etc.) as undefined.
 *
 * Truthful contracts:
 *   getGap                → full ResearchGap (14+ fields)
 *   submitGapFeedback     → { id, user_rating?, user_notes? }
 *   updateGapStatus       → { id, status }
 *
 * After mutation success, callers invalidate the canonical getGap/listGaps
 * query and refetch — they do NOT render the partial mutation response as
 * a complete gap.
 */

import type { GapListResponse, ResearchGap } from "@/api/types";
import {
  decodeArray,
  decodeEnum,
  decodeNumber,
  decodeObject,
  decodeString,
  type JsonContract,
  type ResponseDecoder,
} from "./common";

// ── Truthful mutation result types ───────────────────────────────────

export type GapStatus = "identified" | "investigating" | "addressed";

/** What submitGapFeedback actually returns (gaps.py:510-514). */
export interface GapFeedbackMutationResult {
  id: number;
  user_rating?: number | null;
  user_notes?: string | null;
}

/** What updateGapStatus actually returns (gaps.py:536-538). */
export interface GapStatusMutationResult {
  id: number;
  status: GapStatus;
}

// ── Decoders ─────────────────────────────────────────────────────────
//
// F1.1a-4: ResearchGap is decoded COMPLETELY — every declared field is
// validated, not just "material" ones. Optional fields are validated when
// present and skipped when null/absent (decodeObject skips null optionals).
// Unknown extra backend fields are preserved via the forward-compat spread
// but remain accessible only as `unknown`, not under typed ResearchGap
// field names.

// Sub-decoders for optional nested types
const truthDecoder = decodeObject<{ frequency: number; confidence: number; evidence_count: number }>({
  required: { frequency: decodeNumber, confidence: decodeNumber, evidence_count: decodeNumber },
});

// RelatedIdea and MatchedPaper are loose-mirrored; validate as objects
// with at least an id. Extra fields pass through as unknown.
const relatedIdeaDecoder = decodeObject<{ id: number }>({
  required: { id: decodeNumber },
});
const matchedPaperDecoder = decodeObject<{ id: number }>({
  required: { id: decodeNumber },
});

const researchGapDecoder: ResponseDecoder<ResearchGap> = {
  decode(value, ctx) {
    const dec = decodeObject<ResearchGap>({
      required: {
        id: decodeNumber,
        title: decodeString,
        description: decodeString,
        gap_type: decodeString,
        confidence: decodeNumber,
        potential_impact: decodeString,
        idea_count: decodeNumber,
      },
      optional: {
        pipeline_run_id: decodeNumber,
        truth: truthDecoder,
        related_clusters: decodeArray(decodeNumber),
        related_ideas: decodeArray(relatedIdeaDecoder),
        matched_papers_preview: decodeArray(matchedPaperDecoder),
        status: decodeString,
        user_rating: decodeNumber,
        user_notes: decodeString,
      },
    });
    return dec.decode(value, ctx);
  },
};

const getGapResponseDecoder = decodeObject<{ gap: ResearchGap }>({
  required: { gap: researchGapDecoder },
});

const gapFeedbackResultDecoder = decodeObject<GapFeedbackMutationResult>({
  required: { id: decodeNumber },
  optional: {
    user_rating: decodeNumber,
    user_notes: decodeString,
  },
});

const gapStatusResultDecoder = decodeObject<GapStatusMutationResult>({
  required: {
    id: decodeNumber,
    status: decodeEnum<GapStatus>(["identified", "investigating", "addressed"]),
  },
});

// ── Contracts (F1.1a: discriminated JsonContract) ────────────────────

export const getGapContract: JsonContract<{ gap: ResearchGap }> = {
  id: "gaps.getGap",
  method: "GET",
  pathPattern: "/gaps/{id}",
  responseKind: "json",
  decoder: getGapResponseDecoder,
};

// F1.7a — listGaps (GET /gaps with optional query params).
// Each gap is decoded via the same researchGapDecoder used by getGap, so the
// list path gets the same field-level validation as the detail path. The
// list endpoint omits some optional fields (related_ideas,
// matched_papers_preview, pipeline_run_id) — those are declared optional on
// ResearchGap and skipped by decodeObject when absent.
export const listGapsContract: JsonContract<GapListResponse> = {
  id: "gaps.listGaps",
  method: "GET",
  pathPattern: "/gaps",
  responseKind: "json",
  decoder: decodeObject<GapListResponse>({
    required: {
      gaps: decodeArray(researchGapDecoder),
      total: decodeNumber,
    },
  }),
};

export const submitGapFeedbackContract: JsonContract<{ gap: GapFeedbackMutationResult }> = {
  id: "gaps.submitGapFeedback",
  method: "POST",
  pathPattern: "/gaps/{gapId}/feedback",
  responseKind: "json",
  decoder: decodeObject<{ gap: GapFeedbackMutationResult }>({
    required: { gap: gapFeedbackResultDecoder },
  }),
};

export const updateGapStatusContract: JsonContract<{ gap: GapStatusMutationResult }> = {
  id: "gaps.updateGapStatus",
  method: "PATCH",
  pathPattern: "/gaps/{gapId}/status",
  responseKind: "json",
  decoder: decodeObject<{ gap: GapStatusMutationResult }>({
    required: { gap: gapStatusResultDecoder },
  }),
};
