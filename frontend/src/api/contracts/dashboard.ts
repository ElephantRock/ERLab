/**
 * F1.3a — Dashboard endpoint contracts.
 *
 * Migrates the four dashboard reads from apiFetchUnchecked to JsonContract
 * with runtime decoders. Each decoder validates material fields (IDs,
 * counts, statuses) and preserves optional fields when present.
 *
 * Backend sources:
 *   GET /pipeline/runs   → { runs: PipelineRunSummary[], total: number }
 *   GET /ideas            → { ideas: IdeaSummary[], total: number, score_guide: {...} }
 *   GET /governance/pending → { pending: PendingApproval[] }
 *   GET /ops/dashboard    → OpsDashboard (complex nested object)
 */

import {
  decodeArray,
  decodeNumber,
  decodeObject,
  decodeString,
  type JsonContract,
} from "./common";
import type { PipelineRunSummary, IdeaSummary } from "@/api/types";
import type { PendingApproval } from "@/api/governance";
import type { OpsDashboard } from "@/api/ops";

// ── PipelineRunSummary decoder ───────────────────────────────────────

const runSummaryDecoder = decodeObject<PipelineRunSummary>({
  required: {
    id: decodeNumber,
    domain: decodeString,
    created_at: decodeString,
  },
  optional: {
    status: decodeString,
    current_stage: decodeString,
    ideas_count: decodeNumber,
    session_id: decodeString,
    completed_at: decodeString,
    error_message: decodeString,
    strategy: decodeString,
  },
});

export const listRunsContract: JsonContract<{ runs: PipelineRunSummary[]; total: number }> = {
  id: "pipeline.listRuns",
  method: "GET",
  pathPattern: "/pipeline/runs",
  responseKind: "json",
  decoder: decodeObject<{ runs: PipelineRunSummary[]; total: number }>({
    required: {
      runs: decodeArray(runSummaryDecoder),
      total: decodeNumber,
    },
  }),
};

// ── IdeaSummary decoder (material fields only — quality_summary, governance_status optional) ──

const booleanDecoder = { decode(v: unknown) { return typeof v === "boolean" ? v : false; } };

const ideaSummaryDecoder = decodeObject<IdeaSummary>({
  required: {
    id: decodeNumber,
    title: decodeString,
    domain: decodeString,
    has_proposal: booleanDecoder,
    created_at: decodeString,
  },
  optional: {
    novelty_score: decodeNumber,
    feasibility_score: decodeNumber,
    overall_score: decodeNumber,
    pipeline_run_id: decodeNumber,
    source_gap_ids: decodeArray(decodeString),
  },
});

export const listIdeasContract: JsonContract<{ ideas: IdeaSummary[]; total: number }> = {
  id: "ideas.listIdeas",
  method: "GET",
  pathPattern: "/ideas",
  responseKind: "json",
  decoder: decodeObject<{ ideas: IdeaSummary[]; total: number }>({
    required: {
      ideas: decodeArray(ideaSummaryDecoder),
      total: decodeNumber,
    },
  }),
};

// ── Governance pending decoder ───────────────────────────────────────

const pendingApprovalDecoder = decodeObject<PendingApproval>({
  required: {
    id: decodeString,
    type: decodeString,
    summary: decodeString,
  },
});

export const getPendingContract: JsonContract<{ pending: PendingApproval[] }> = {
  id: "governance.getPending",
  method: "GET",
  pathPattern: "/governance/pending",
  responseKind: "json",
  decoder: decodeObject<{ pending: PendingApproval[] }>({
    required: { pending: decodeArray(pendingApprovalDecoder) },
  }),
};

// ── OpsDashboard decoder ─────────────────────────────────────────────
// OpsDashboard is a deeply nested object. Material fields: window.days,
// run_health totals. Optional/nested structures validated as objects.

export const getOpsDashboardContract: JsonContract<OpsDashboard> = {
  id: "ops.getOpsDashboard",
  method: "GET",
  pathPattern: "/ops/dashboard",
  responseKind: "json",
  decoder: {
    decode(value, ctx) {
      // Validate material structural fields, then return the full object.
      // OpsDashboard has deeply nested optional sub-objects; validating every
      // declared field would be enormous. This decoder verifies the top-level
      // object shape + material identity fields (window.days, run_health totals).
      const materialCheck = decodeObject<{ window: { days: number }; run_health: { total_runs: number } }>({
        required: {
          window: decodeObject({ required: { days: decodeNumber } }),
          run_health: decodeObject({ required: { total_runs: decodeNumber } }),
        },
      });
      materialCheck.decode(value, ctx);
      // Material fields validated; return the full object as OpsDashboard.
      return value as OpsDashboard;
    },
  },
};
