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

import type { ResearchGap } from "@/api/types";
import {
  decodeNumber,
  decodeObject,
  decodeString,
  decodeEnum,
  type EndpointContract,
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
// For getGap, the full ResearchGap shape is validated on material fields
// (id, title, status-bearing fields) and trusted on optional/unknown
// fields — the backend genuinely returns the full gap there. For mutations,
// only the fields actually returned are decoded.

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

// getGap response: { gap: ResearchGap }. The decoder validates MATERIAL
// fields of the gap (id, title — identity/display) and preserves all
// extra backend fields via decodeObject's forward-compat spread. The
// returned object is typed as ResearchGap because the backend genuinely
// returns the full shape here (gaps.py:378-393), and the material fields
// are runtime-verified. Optional fields are trusted when present.
const researchGapDecoder = decodeObject<ResearchGap>({
  required: { id: decodeNumber, title: decodeString },
});

const getGapResponseDecoder = decodeObject<{ gap: ResearchGap }>({
  required: { gap: researchGapDecoder },
});

// ── Contracts ────────────────────────────────────────────────────────

export const getGapContract: EndpointContract<{ gap: ResearchGap }> = {
  id: "gaps.getGap",
  method: "GET",
  pathPattern: "/gaps/{id}",
  emptyBody: "forbidden",
  decodeResponse: getGapResponseDecoder,
};

export const submitGapFeedbackContract: EndpointContract<{ gap: GapFeedbackMutationResult }> = {
  id: "gaps.submitGapFeedback",
  method: "POST",
  pathPattern: "/gaps/{gapId}/feedback",
  emptyBody: "forbidden",
  decodeResponse: decodeObject<{ gap: GapFeedbackMutationResult }>({
    required: { gap: gapFeedbackResultDecoder },
  }),
};

export const updateGapStatusContract: EndpointContract<{ gap: GapStatusMutationResult }> = {
  id: "gaps.updateGapStatus",
  method: "PATCH",
  pathPattern: "/gaps/{gapId}/status",
  emptyBody: "forbidden",
  decodeResponse: decodeObject<{ gap: GapStatusMutationResult }>({
    required: { gap: gapStatusResultDecoder },
  }),
};
