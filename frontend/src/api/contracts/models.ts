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
  decodeObject,
  decodeString,
  decodeStringRecord,
  type JsonContract,
} from "./common";

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
