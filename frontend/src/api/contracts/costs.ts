/**
 * F1.7a — Cost endpoint contracts (summary, by-provider/stage/model,
 * run-breakdown).
 *
 * Migrates the five remaining apiFetchUnchecked callers in src/api/costs.ts
 * to JsonContract + runtime decoders. The by-provider/stage/model endpoints
 * return `Record<string, BreakdownEntry>` — a homogeneous object map. There
 * is no decodeRecord primitive in common.ts (decodeStringRecord only accepts
 * string values), so `decodeBreakdownRecord` below mirrors that decoder's
 * shape but validates each value as a BreakdownEntry.
 *
 * Backend sources (backend/api/routes/costs.py):
 *   GET /costs/summary     → CostSummary
 *   GET /costs/by-provider → Record<string, BreakdownEntry>
 *   GET /costs/by-stage    → Record<string, BreakdownEntry>
 *   GET /costs/by-model    → Record<string, BreakdownEntry>
 *   GET /costs/run/{run_id} → RunCostBreakdown
 */

import type {
  BreakdownEntry,
  CostSummary,
  ModelBreakdown,
  ProviderBreakdown,
  RunCostBreakdown,
  StageBreakdown,
} from "@/api/costs";
import {
  ApiContractError,
  decodeNumber,
  decodeObject,
  decodeString,
  type JsonContract,
  type ResponseDecoder,
} from "./common";

// ── Decoders ─────────────────────────────────────────────────────────

const costSummaryDecoder = decodeObject<CostSummary>({
  required: {
    total_cost_usd: decodeNumber,
    total_tokens: decodeNumber,
    event_count: decodeNumber,
  },
});

const breakdownEntryDecoder = decodeObject<BreakdownEntry>({
  required: {
    cost_usd: decodeNumber,
    input_tokens: decodeNumber,
    output_tokens: decodeNumber,
    calls: decodeNumber,
  },
});

/**
 * Decoder for `Record<string, BreakdownEntry>` — a homogeneous object whose
 * values must each be a valid BreakdownEntry. Mirrors decodeStringRecord but
 * validates the entry shape instead of a plain string. An empty object `{}`
 * is valid (no breakdown entries for this slice).
 */
function decodeBreakdownRecord<T extends Record<string, BreakdownEntry>>(): ResponseDecoder<T> {
  return {
    decode(value, ctx) {
      if (typeof value !== "object" || value === null || Array.isArray(value)) {
        throw new ApiContractError(
          "api_response_contract_mismatch",
          ctx.endpointId,
          `expected object (breakdown record), got ${value === null ? "null" : Array.isArray(value) ? "array" : typeof value}`,
          200,
        );
      }
      const obj = value as Record<string, unknown>;
      const out: Record<string, BreakdownEntry> = {};
      for (const [k, v] of Object.entries(obj)) {
        out[k] = breakdownEntryDecoder.decode(v, ctx);
      }
      return out as unknown as T;
    },
  };
}

const runCostBreakdownDecoder = decodeObject<RunCostBreakdown>({
  required: {
    run_id: decodeString,
    summary: costSummaryDecoder,
    by_provider: decodeBreakdownRecord<ProviderBreakdown>(),
    by_stage: decodeBreakdownRecord<StageBreakdown>(),
  },
});

// ── Contracts ────────────────────────────────────────────────────────

export const getCostSummaryContract: JsonContract<CostSummary> = {
  id: "costs.getCostSummary",
  method: "GET",
  pathPattern: "/costs/summary",
  responseKind: "json",
  decoder: costSummaryDecoder,
};

export const getCostByProviderContract: JsonContract<ProviderBreakdown> = {
  id: "costs.getCostByProvider",
  method: "GET",
  pathPattern: "/costs/by-provider",
  responseKind: "json",
  decoder: decodeBreakdownRecord<ProviderBreakdown>(),
};

export const getCostByStageContract: JsonContract<StageBreakdown> = {
  id: "costs.getCostByStage",
  method: "GET",
  pathPattern: "/costs/by-stage",
  responseKind: "json",
  decoder: decodeBreakdownRecord<StageBreakdown>(),
};

export const getCostByModelContract: JsonContract<ModelBreakdown> = {
  id: "costs.getCostByModel",
  method: "GET",
  pathPattern: "/costs/by-model",
  responseKind: "json",
  decoder: decodeBreakdownRecord<ModelBreakdown>(),
};

export const getRunCostBreakdownContract: JsonContract<RunCostBreakdown> = {
  id: "costs.getRunCostBreakdown",
  method: "GET",
  pathPattern: "/costs/run/{runId}",
  responseKind: "json",
  decoder: runCostBreakdownDecoder,
};
