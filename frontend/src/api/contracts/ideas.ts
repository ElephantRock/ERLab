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

import type { EnsembleReview, PerspectiveReview } from "@/api/types";
import {
  decodeArray,
  decodeNumber,
  decodeObject,
  decodeString,
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
