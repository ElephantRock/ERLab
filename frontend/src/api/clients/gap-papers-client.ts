/**
 * F1.2 — Typed client for the gap-papers endpoint contract.
 *
 * Routes through callContract → JsonContract<GapPapersResult> → apiFetchJson.
 * Does NOT use apiFetchUnchecked — the unchecked-caller budget is unaffected.
 */

import { callContract } from "@/api/contracts/common";
import { getGapPapersContract, type GapPapersResult } from "@/api/contracts/gap-papers";

export function getGapPapers(gapId: number): Promise<GapPapersResult> {
  return callContract(getGapPapersContract, { params: { gapId } });
}

export type { GapPapersResult };
