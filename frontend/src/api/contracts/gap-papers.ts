/**
 * F1.2 — Gap-papers endpoint contract.
 *
 * Backend: GET /gaps/{gap_id}/papers (gaps.py:400-437)
 * Returns: { papers: MatchedPaper[], total: number }
 *
 * The endpoint returns up to 20 papers (capped). `total` is the real
 * count. The decoder validates every declared field of MatchedPaper
 * and enforces total >= papers.length.
 */

import type { MatchedPaper } from "@/api/types";
import {
  ApiContractError,
  decodeArray,
  decodeNumber,
  decodeObject,
  decodeString,
  type JsonContract,
  type ResponseDecoder,
} from "./common";

export interface GapPapersResult {
  papers: MatchedPaper[];
  total: number;
}

/** Complete MatchedPaper decoder — every declared field validated. */
const matchedPaperDecoder: ResponseDecoder<MatchedPaper> = {
  decode(value, ctx) {
    const dec = decodeObject<MatchedPaper>({
      required: {
        id: decodeNumber,
        title: decodeString,
      },
      optional: {
        abstract: decodeString,
        year: decodeNumber,
        venue: decodeString,
        citation_count: decodeNumber,
      },
    });
    return dec.decode(value, ctx);
  },
};

/**
 * GapPapersResult decoder. Validates papers as an array of completely
 * decoded MatchedPaper records, and total as a non-negative safe integer.
 * Enforces papers.length <= total.
 */
export const gapPapersDecoder: ResponseDecoder<GapPapersResult> = {
  decode(value, ctx) {
    const dec = decodeObject<GapPapersResult>({
      required: {
        papers: decodeArray(matchedPaperDecoder),
        total: decodeNumber,
      },
    });
    const result = dec.decode(value, ctx);
    // Enforce total >= papers.length
    if (result.total < 0) {
      throw new ApiContractError(
        "api_response_contract_mismatch",
        ctx.endpointId,
        `total is negative (${result.total})`,
        200,
      );
    }
    if (result.papers.length > result.total) {
      throw new ApiContractError(
        "api_response_contract_mismatch",
        ctx.endpointId,
        `papers.length (${result.papers.length}) > total (${result.total})`,
        200,
      );
    }
    return result;
  },
};

export const getGapPapersContract: JsonContract<GapPapersResult> = {
  id: "gaps.getGapPapers",
  method: "GET",
  pathPattern: "/gaps/{gapId}/papers",
  responseKind: "json",
  decoder: gapPapersDecoder,
};
