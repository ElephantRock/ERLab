/**
 * F1.7a — Autonomous control endpoint contracts (stop cycle, scheduler).
 *
 * Migrates the three remaining apiFetchUnchecked callers in
 * src/api/autonomous.ts to JsonContract + runtime decoders. These are POST
 * control endpoints; their `status` field is the material signal that the
 * UI renders (stopped / running / not_configured). cycle_id on the stop
 * response echoes the request and is used for confirmation.
 *
 * Backend sources (backend/api/routes/pipeline.py):
 *   POST /pipeline/autonomous/stop?cycle_id=... → { status, cycle_id }
 *   POST /pipeline/scheduler/start             → { status, interval_seconds? }
 *   POST /pipeline/scheduler/stop              → { status }
 *
 * `status` is left as decodeString (not a closed enum): the backend returns
 * a small but not formally-contractually-closed vocabulary ("stopped",
 * "running", "not_configured", plus an optional `message` on the
 * not_configured branch) and the UI only checks equality against specific
 * values — a strict enum would couple the frontend to every backend string.
 */

import {
  decodeNumber,
  decodeObject,
  decodeString,
  type JsonContract,
} from "./common";

// ── Decoders ─────────────────────────────────────────────────────────

const stopCycleResponseDecoder = decodeObject<{ status: string; cycle_id: string }>({
  required: {
    status: decodeString,
    cycle_id: decodeString,
  },
});

const startSchedulerResponseDecoder = decodeObject<{
  status: string;
  interval_seconds?: number;
}>({
  required: {
    status: decodeString,
  },
  optional: {
    interval_seconds: decodeNumber,
  },
});

const stopSchedulerResponseDecoder = decodeObject<{ status: string }>({
  required: {
    status: decodeString,
  },
});

// ── Contracts ────────────────────────────────────────────────────────

export const stopAutonomousCycleContract: JsonContract<{
  status: string;
  cycle_id: string;
}> = {
  id: "autonomous.stopAutonomousCycle",
  method: "POST",
  pathPattern: "/pipeline/autonomous/stop",
  responseKind: "json",
  decoder: stopCycleResponseDecoder,
};

export const startSchedulerContract: JsonContract<{
  status: string;
  interval_seconds?: number;
}> = {
  id: "autonomous.startScheduler",
  method: "POST",
  pathPattern: "/pipeline/scheduler/start",
  responseKind: "json",
  decoder: startSchedulerResponseDecoder,
};

export const stopSchedulerContract: JsonContract<{ status: string }> = {
  id: "autonomous.stopScheduler",
  method: "POST",
  pathPattern: "/pipeline/scheduler/stop",
  responseKind: "json",
  decoder: stopSchedulerResponseDecoder,
};
