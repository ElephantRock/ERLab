/**
 * F1.1 — Stage-model endpoint contracts (H1 repair).
 *
 * The pre-F1.1 `stage-model-selector.tsx` made three raw `fetch()` calls to
 * `/settings/models` (GET/PUT/DELETE), bypassing `apiFetchUnchecked` entirely — no
 * `X-API-Key`/JWT auth headers, no `ApiError` normalization, and using
 * `import.meta.env.VITE_API_URL` instead of `getApiUrl()` (ignoring the
 * user-configured base URL). This would silently fail in any deployment
 * with auth enabled.
 *
 * These contracts migrate all three operations through the canonical
 * `apiFetchUnchecked` transport + runtime decoders.
 *
 * Backend source of truth: backend/api/routes/model_config.py
 *   GET    /settings/models  → {models, stages, assignments}
 *   PUT    /settings/models  → {assignments, message}
 *   DELETE /settings/models  → {assignments: {}, message}
 */

import {
  decodeArray,
  decodeBoolean,
  decodeEnum,
  decodeNumber,
  decodeObject,
  decodeString,
  decodeStringRecord,
  type JsonContract,
} from "./common";
import type {
  AssignmentsResponse,
  CatalogModel,
  CatalogResponse,
  GpuInfo,
  OverrideUpdateResponse,
  OverrideValidateResponse,
  OverrideWarning,
  OverridesResponse,
  StageAssignment,
  StageInfo,
  StagesResponse,
} from "@/api/settings";

// ── Domain types (authoritative for this endpoint) ───────────────────

export interface StageModelOption {
  id: string;
  name: string;
  provider: string;
  model: string;
  location: string;
  type: string;
}

export interface StageModelStageInfo {
  name: string;
  label: string;
  category: string;
  default_model: string;
}

export interface StageModelConfig {
  models: StageModelOption[];
  stages: StageModelStageInfo[];
  assignments: Record<string, string>;
}

/** PUT response — backend returns {assignments, message} (model_config.py:243). */
export interface StageModelUpdateResult {
  assignments: Record<string, string>;
  message: string;
}

/** DELETE response — backend returns {assignments: {}, message} (model_config.py:254). */
export interface StageModelResetResult {
  assignments: Record<string, string>;
  message: string;
}

// ── Decoders ─────────────────────────────────────────────────────────

const modelOptionDecoder = decodeObject<StageModelOption>({
  required: {
    id: decodeString,
    name: decodeString,
    provider: decodeString,
    model: decodeString,
    location: decodeString,
    type: decodeString,
  },
});

const stageInfoDecoder = decodeObject<StageModelStageInfo>({
  required: {
    name: decodeString,
    label: decodeString,
    category: decodeString,
    default_model: decodeString,
  },
});

// ── Contracts ────────────────────────────────────────────────────────

export const getStageModelConfigContract: JsonContract<StageModelConfig> = {
  id: "models.getStageModelConfig",
  method: "GET",
  pathPattern: "/settings/models",
  responseKind: "json",
  decoder: decodeObject<StageModelConfig>({
    required: {
      models: decodeArray(modelOptionDecoder),
      stages: decodeArray(stageInfoDecoder),
      assignments: decodeStringRecord,
    },
  }),
};

export const updateStageModelConfigContract: JsonContract<StageModelUpdateResult> = {
  id: "models.updateStageModelConfig",
  method: "PUT",
  pathPattern: "/settings/models",
  responseKind: "json",
  decoder: decodeObject<StageModelUpdateResult>({
    required: {
      assignments: decodeStringRecord,
      message: decodeString,
    },
  }),
};

export const resetStageModelConfigContract: JsonContract<StageModelResetResult> = {
  id: "models.resetStageModelConfig",
  method: "DELETE",
  pathPattern: "/settings/models",
  responseKind: "json",
  decoder: decodeObject<StageModelResetResult>({
    required: {
      assignments: decodeStringRecord,
      message: decodeString,
    },
  }),
};

// ═══════════════════════════════════════════════════════════════════════
// F1.7a — Settings catalog / assignments / stages / overrides contracts.
// These migrate the remaining apiFetchUnchecked callers in src/api/settings.ts.
//
// Backend sources (backend/api/routes/model_config.py):
//   GET    /settings/catalog            → CatalogResponse
//   GET    /settings/assignments        → AssignmentsResponse
//   GET    /settings/stages             → StagesResponse
//   PUT    /settings/overrides          → OverrideUpdateResponse
//   POST   /settings/overrides/validate → OverrideValidateResponse
//   DELETE /settings/overrides/{stage}  → { message, overrides }
//   DELETE /settings/overrides          → { message, overrides }
//
// Note: getCertificationContract + getOverridesContract already live in
// f1-3a-reads.ts (migrated in F1.3a). The contracts below cover the seven
// remaining settings callers.
// ═══════════════════════════════════════════════════════════════════════

// ── Catalog sub-decoders ─────────────────────────────────────────────
// CatalogModel has nested capabilities (4 bool flags) + an optional
// measured stats object. All are validated when present. gpu is optional
// and nullable — validated as an object when present.

const modelCapabilitiesDecoder = decodeObject<{
  json_mode: boolean;
  tools: boolean;
  vision: boolean;
  thinking: boolean;
}>({
  required: {
    json_mode: decodeBoolean,
    tools: decodeBoolean,
    vision: decodeBoolean,
    thinking: decodeBoolean,
  },
});

const modelMeasuredStatsDecoder = decodeObject<{
  total_calls: number;
  reliability: number;
  json_reliability: number;
}>({
  required: {
    total_calls: decodeNumber,
    reliability: decodeNumber,
    json_reliability: decodeNumber,
  },
});

const catalogModelDecoder = decodeObject<CatalogModel>({
  required: {
    model_id: decodeString,
    display_name: decodeString,
    provider_type: decodeString,
    endpoint_url: decodeString,
    parameter_count: decodeString,
    context_length: decodeNumber,
    context_label: decodeString,
    quantization: decodeString,
    size_gb: decodeNumber,
    capabilities: modelCapabilitiesDecoder,
    is_loaded: decodeBoolean,
    health_status: decodeString,
  },
  optional: {
    measured: modelMeasuredStatsDecoder,
  },
});

const gpuInfoDecoder = decodeObject<GpuInfo>({
  required: {
    name: decodeString,
    vram_total_gb: decodeNumber,
    vram_available_gb: decodeNumber,
  },
});

export const getCatalogContract: JsonContract<CatalogResponse> = {
  id: "settings.getCatalog",
  method: "GET",
  pathPattern: "/settings/catalog",
  responseKind: "json",
  decoder: decodeObject<CatalogResponse>({
    required: {
      models: decodeArray(catalogModelDecoder),
      total: decodeNumber,
    },
    optional: {
      gpu: gpuInfoDecoder,
      error: decodeString,
    },
  }),
};

// ── Assignments decoder ──────────────────────────────────────────────
// AssignmentsResponse.assignments is Record<string, StageAssignment> — each
// value is a nested object with model_id + flags. The custom decoder
// validates the envelope (assignments object + total_stages count) then
// validates each assignment value as a StageAssignment.

const stageAssignmentDecoder = decodeObject<StageAssignment>({
  required: {
    model_id: decodeString,
    parameter_count: decodeString,
    context_label: decodeString,
    is_loaded: decodeBoolean,
    quantization: decodeString,
  },
});

const assignmentsEnvelopeDecoder = decodeObject<{
  assignments: Record<string, unknown>;
  total_stages: number;
  error?: string;
}>({
  required: {
    assignments: decodeObject<Record<string, unknown>>({ required: {} }),
    total_stages: decodeNumber,
  },
  optional: {
    error: decodeString,
  },
});

const assignmentsResponseDecoder: JsonContract<AssignmentsResponse>["decoder"] = {
  decode(value, ctx) {
    const envelope = assignmentsEnvelopeDecoder.decode(value, ctx);
    // Validate each assignment value is a StageAssignment
    const validated: Record<string, StageAssignment> = {};
    for (const [k, v] of Object.entries(envelope.assignments)) {
      validated[k] = stageAssignmentDecoder.decode(v, ctx);
    }
    return {
      ...(value as Record<string, unknown>),
      assignments: validated,
      total_stages: envelope.total_stages,
      ...(envelope.error !== undefined ? { error: envelope.error } : {}),
    } as AssignmentsResponse;
  },
};

export const getAssignmentsContract: JsonContract<AssignmentsResponse> = {
  id: "settings.getAssignments",
  method: "GET",
  pathPattern: "/settings/assignments",
  responseKind: "json",
  decoder: assignmentsResponseDecoder,
};

// ── Stages decoder ───────────────────────────────────────────────────
// StageInfo.category is a closed enum ("thinking" | "generation" | "passthrough").

const settingsStageInfoDecoder = decodeObject<StageInfo>({
  required: {
    name: decodeString,
    label: decodeString,
    category: decodeEnum<StageInfo["category"]>(["thinking", "generation", "passthrough"]),
    needs_llm: decodeBoolean,
  },
});

export const getStagesContract: JsonContract<StagesResponse> = {
  id: "settings.getStages",
  method: "GET",
  pathPattern: "/settings/stages",
  responseKind: "json",
  decoder: decodeObject<StagesResponse>({
    required: {
      stages: decodeArray(settingsStageInfoDecoder),
      total: decodeNumber,
    },
  }),
};

// ── Override warning decoder ─────────────────────────────────────────
// Shared by updateOverrides + validateOverrides responses.

const overrideWarningDecoder = decodeObject<OverrideWarning>({
  required: {
    code: decodeString,
    stage: decodeString,
    model_id: decodeString,
    message: decodeString,
  },
});

// ── updateOverrides decoder ──────────────────────────────────────────
// PUT /settings/overrides → { overrides, warnings, message?, dry_run? }.
// The dry_run path returns dry_run: true and no message.

export const updateOverridesContract: JsonContract<OverrideUpdateResponse> = {
  id: "settings.updateOverrides",
  method: "PUT",
  pathPattern: "/settings/overrides",
  responseKind: "json",
  decoder: decodeObject<OverrideUpdateResponse>({
    required: {
      overrides: decodeStringRecord,
      warnings: decodeArray(overrideWarningDecoder),
    },
    optional: {
      message: decodeString,
      dry_run: decodeBoolean,
    },
  }),
};

// ── validateOverrides decoder ────────────────────────────────────────
// POST /settings/overrides/validate → { valid, overrides, warnings }.

export const validateOverridesContract: JsonContract<OverrideValidateResponse> = {
  id: "settings.validateOverrides",
  method: "POST",
  pathPattern: "/settings/overrides/validate",
  responseKind: "json",
  decoder: decodeObject<OverrideValidateResponse>({
    required: {
      valid: decodeBoolean,
      overrides: decodeStringRecord,
      warnings: decodeArray(overrideWarningDecoder),
    },
  }),
};

// ── removeOverride + clearAllOverrides decoder ───────────────────────
// Both return { message, overrides: Record<string,string> }.

const overrideMutationResultDecoder = decodeObject<{ message: string; overrides: Record<string, string> }>({
  required: {
    message: decodeString,
    overrides: decodeStringRecord,
  },
});

export const removeOverrideContract: JsonContract<{ message: string; overrides: Record<string, string> }> = {
  id: "settings.removeOverride",
  method: "DELETE",
  pathPattern: "/settings/overrides/{stage}",
  responseKind: "json",
  decoder: overrideMutationResultDecoder,
};

export const clearOverridesContract: JsonContract<{ message: string; overrides: Record<string, string> }> = {
  id: "settings.clearOverrides",
  method: "DELETE",
  pathPattern: "/settings/overrides",
  responseKind: "json",
  decoder: overrideMutationResultDecoder,
};

// Re-export so consumers reading models.ts see the full settings contract surface.
export type { OverridesResponse };
