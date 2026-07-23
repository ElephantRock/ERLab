/**
 * F1.7a — Pipeline endpoint contracts.
 *
 * Migrates the pipeline mutation/detail endpoints from apiFetchUnchecked to
 * JsonContract with runtime decoders. listRuns already lives in
 * contracts/dashboard.ts (it was migrated in F1.3a) and is the canonical
 * list-reads contract — pipeline.ts imports and re-uses it.
 *
 * Backend sources (backend/api/routes/pipeline.py):
 *   POST   /pipeline/run                  → { run_id, status, preflight }
 *   GET    /pipeline/runs/detail/{id}     → PipelineRunDetail
 *   DELETE /pipeline/runs/{run_id}        → { status, run_id }
 *   GET    /pipeline/runs/{run_id}/ideas  → { ideas: IdeaSummary[], total }
 *   POST   /pipeline/resume/{run_id}      → { status, run_id, ideas_count, gaps_count, proposals_count }
 *   GET    /pipeline/estimate             → EstimateResponse
 *   POST   /pipeline/autonomous           → AutonomousCycleResponse
 *
 * The detail endpoint returns a wider shape than PipelineRunSummary (extra
 * config / stages_completed / ideas / tree_data). Its material identity
 * fields (id, status, domain, created_at) plus the array structure for
 * stages_completed and ideas are validated; nested config/tree pass through
 * via decodeObject's forward-compat spread.
 */

import {
  decodeArray,
  decodeBoolean,
  decodeEnum,
  decodeNumber,
  decodeObject,
  decodeString,
  type JsonContract,
  type ResponseDecoder,
} from "./common";
import type {
  AutonomousCycleResponse,
  IdeaSummary,
  PipelineRunDetail,
  PipelineRunSummary,
  TriggerRunResponse,
} from "@/api/types";
import type { EstimateResponse } from "@/api/pipeline";

// ── Sub-decoders shared between listRuns (dashboard) and getRunDetail ──
//
// PipelineRunSummary.status is a closed enum
// ("pending" | "running" | "completed" | "failed"). The detail endpoint
// returns the same status field, so the enum is enforced on both reads.
// (getRunDetail is allowed to add a future "stale" boolean; status stays in
// the closed vocabulary.)

const runStatusDecoder = decodeEnum<PipelineRunSummary["status"]>([
  "pending",
  "running",
  "completed",
  "failed",
]);

const runDetailIdeaDecoder = decodeObject<IdeaSummary>({
  required: {
    id: decodeNumber,
    title: decodeString,
  },
  optional: {
    domain: decodeString,
    novelty_score: decodeNumber,
    feasibility_score: decodeNumber,
    overall_score: decodeNumber,
    has_proposal: decodeBoolean,
    pipeline_run_id: decodeNumber,
    created_at: decodeString,
  },
});

// ── getRunDetail decoder ──────────────────────────────────────────────
// Material fields: id (key), status, domain, created_at. stages_completed
// is an array of strings (drives progress display). ideas is an array of
// objects (each must have an id + title). config / tree_data are nested and
// forward-compat — preserved via spread. The decoder is declared against
// PipelineRunDetail so callers see the full typed value.

export const runDetailDecoder: ResponseDecoder<PipelineRunDetail> = {
  decode(value, ctx) {
    const dec = decodeObject<PipelineRunDetail>({
      required: {
        id: decodeNumber,
        status: runStatusDecoder,
        domain: decodeString,
        created_at: decodeString,
        stages_completed: decodeArray(decodeString),
        ideas: decodeArray(runDetailIdeaDecoder),
      },
      optional: {
        current_stage: decodeString,
        ideas_count: decodeNumber,
        session_id: decodeString,
        completed_at: decodeString,
        error_message: decodeString,
        strategy: decodeString,
      },
    });
    return dec.decode(value, ctx);
  },
};

// ── triggerRun decoder ────────────────────────────────────────────────
// POST /pipeline/run → { run_id, status, preflight }. The 202 response
// returns run_id + status immediately. preflight is a nested object that
// the caller reads for can_proceed — validated as a material sub-object.

const preflightDecoder = decodeObject<{ can_proceed: boolean }>({
  required: { can_proceed: decodeBoolean },
});

const triggerRunResponseDecoder = decodeObject<TriggerRunResponse & { preflight?: { can_proceed: boolean; warnings?: unknown[] } }>({
  required: {
    run_id: decodeString,
    status: decodeString,
  },
  optional: {
    preflight: preflightDecoder,
  },
});

// ── cancelRun decoder ─────────────────────────────────────────────────
// DELETE /pipeline/runs/{run_id} → { status: "cancelling", run_id }.

const cancelRunResponseDecoder = decodeObject<{ status: string; run_id: string }>({
  required: {
    status: decodeString,
    run_id: decodeString,
  },
});

// ── getRunIdeas decoder ───────────────────────────────────────────────
// GET /pipeline/runs/{run_id}/ideas → { ideas: IdeaSummary[], total }.
// The backend returns a partial IdeaSummary (id, title, scores) — validate
// the material id + title and preserve the rest via spread.

const runIdeaDecoder = decodeObject<IdeaSummary>({
  required: {
    id: decodeNumber,
    title: decodeString,
  },
  optional: {
    domain: decodeString,
    novelty_score: decodeNumber,
    feasibility_score: decodeNumber,
    overall_score: decodeNumber,
    created_at: decodeString,
  },
});

const runIdeasResponseDecoder = decodeObject<{ ideas: IdeaSummary[]; total: number }>({
  required: {
    ideas: decodeArray(runIdeaDecoder),
    total: decodeNumber,
  },
});

// ── resumeRun decoder ─────────────────────────────────────────────────
// POST /pipeline/resume/{run_id} → { status, run_id, ideas_count,
// gaps_count, proposals_count }.

const resumeRunResponseDecoder = decodeObject<{
  status: string;
  run_id: string;
  ideas_count: number;
  gaps_count: number;
  proposals_count: number;
}>({
  required: {
    status: decodeString,
    run_id: decodeString,
    ideas_count: decodeNumber,
    gaps_count: decodeNumber,
    proposals_count: decodeNumber,
  },
});

// ── estimate decoder ──────────────────────────────────────────────────
// GET /pipeline/estimate → EstimateResponse. Material fields are the
// scalar cost/time numbers + the breakdown array (each row has stage +
// model + token counts). strategy + stages identify the estimate.

const estimateBreakdownDecoder = decodeObject<{
  stage: string;
  model: string;
  label: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  time_seconds: number;
}>({
  required: {
    stage: decodeString,
    model: decodeString,
    label: decodeString,
    input_tokens: decodeNumber,
    output_tokens: decodeNumber,
    cost_usd: decodeNumber,
    time_seconds: decodeNumber,
  },
});

const estimateResponseDecoder = decodeObject<EstimateResponse>({
  required: {
    strategy: decodeString,
    stages: decodeNumber,
    estimated_cost_usd: decodeNumber,
    estimated_time_seconds: decodeNumber,
    estimated_time_display: decodeString,
    cost_display: decodeString,
    local_cost_usd: decodeNumber,
    cloud_cost_usd: decodeNumber,
    breakdown: decodeArray(estimateBreakdownDecoder),
  },
});

// ── autonomous decoder ────────────────────────────────────────────────
// POST /pipeline/autonomous → AutonomousCycleResponse
// { cycle_id, status, domain, max_runs }.

const autonomousResponseDecoder = decodeObject<AutonomousCycleResponse>({
  required: {
    cycle_id: decodeString,
    status: decodeString,
    domain: decodeString,
    max_runs: decodeNumber,
  },
});

// ── Contracts ─────────────────────────────────────────────────────────

export const triggerRunContract: JsonContract<
  TriggerRunResponse & { preflight?: { can_proceed: boolean; warnings?: unknown[] } }
> = {
  id: "pipeline.triggerRun",
  method: "POST",
  pathPattern: "/pipeline/run",
  responseKind: "json",
  decoder: triggerRunResponseDecoder,
};

export const getRunDetailContract: JsonContract<PipelineRunDetail> = {
  id: "pipeline.getRunDetail",
  method: "GET",
  pathPattern: "/pipeline/runs/detail/{id}",
  responseKind: "json",
  decoder: runDetailDecoder,
};

export const cancelRunContract: JsonContract<{ status: string; run_id: string }> = {
  id: "pipeline.cancelRun",
  method: "DELETE",
  pathPattern: "/pipeline/runs/{runId}",
  responseKind: "json",
  decoder: cancelRunResponseDecoder,
};

export const getRunIdeasContract: JsonContract<{ ideas: IdeaSummary[]; total: number }> = {
  id: "pipeline.getRunIdeas",
  method: "GET",
  pathPattern: "/pipeline/runs/{runId}/ideas",
  responseKind: "json",
  decoder: runIdeasResponseDecoder,
};

export const resumeRunContract: JsonContract<{
  status: string;
  run_id: string;
  ideas_count: number;
  gaps_count: number;
  proposals_count: number;
}> = {
  id: "pipeline.resumeRun",
  method: "POST",
  pathPattern: "/pipeline/resume/{runId}",
  responseKind: "json",
  decoder: resumeRunResponseDecoder,
};

export const getEstimateContract: JsonContract<EstimateResponse> = {
  id: "pipeline.getEstimate",
  method: "GET",
  pathPattern: "/pipeline/estimate",
  responseKind: "json",
  decoder: estimateResponseDecoder,
};

export const triggerAutonomousContract: JsonContract<AutonomousCycleResponse> = {
  id: "pipeline.triggerAutonomous",
  method: "POST",
  pathPattern: "/pipeline/autonomous",
  responseKind: "json",
  decoder: autonomousResponseDecoder,
};
