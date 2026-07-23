/**
 * F1.6.1 — Diagnostics runtime-error contract.
 *
 * Backend: POST /api/v1/diagnostics/runtime-error
 * Returns: { status: "accepted"; event_id: string } with HTTP 202.
 *
 * The diagnostics endpoint is governed anonymous — clients often crash
 * precisely when auth is broken. The backend enforces:
 *   - 8 KiB body cap via ASGI middleware (pre-parser)
 *   - strict Pydantic schema with extra='forbid'
 *   - server-side re-sanitization (route pathname-only, safe event_id chars)
 *   - per-IP rate limit
 *   - origin allowlist
 * See backend/api/routes/diagnostics.py and
 * backend/api/middleware/diagnostics_body_limit.py.
 *
 * F1.6.1 [V3-ack]: the acknowledgment decoder validates the SHAPE only.
 * Equality between the returned event_id and the submitted report's
 * event_id is enforced as a CLIENT POSTCONDITION in
 * sendRuntimeErrorReport (api/clients/diagnostics-client.ts), not in the
 * static decoder — a static decoder cannot know the submitted request ID.
 */

import {
  decodeObject,
  decodeString,
  decodeEnum,
  type JsonContract,
  type ResponseDecoder,
} from "./common";

// ── Request schema (matches backend ClientRuntimeErrorReportV1) ───────

export type RuntimeErrorCode =
  | "render_error"
  | "lazy_route_error"
  | "global_error"
  | "unhandled_rejection";

/**
 * Strict runtime-error report. The sanitizer
 * (lib/runtime-error-sanitizer.ts) constructs this; nothing else should
 * build one by hand. The backend's Pydantic schema mirrors these fields
 * with the same bounds (extra='forbid').
 *
 * SECURITY INVARIANT: never include raw error.message, error.stack,
 * request/response bodies, headers, or tokens. Diagnostic utility comes
 * from event_id, category, normalized error_name, route pathname,
 * sanitized component_stack, build_version, occurred_at — and the
 * allowlisted category message (never raw).
 */
export interface ClientRuntimeErrorReport {
  schema_version: "client_runtime_error_v1";
  event_id: string;
  category: RuntimeErrorCode;
  /** Pathname only — never query or fragment. */
  route: string;
  /** Sanitized component stack; never raw error.stack. Bounded ≤4096. */
  component_stack: string | null;
  /** Normalized error class name; bounded ≤128. */
  error_name: string;
  /** Allowlisted per-category message; never raw Error.message. */
  sanitized_message: string;
  correlation_id: string | null;
  build_version: string | null;
  occurred_at: string;
}

// ── Response schema ───────────────────────────────────────────────────

export interface RuntimeErrorAcknowledgment {
  status: "accepted";
  event_id: string;
}

/**
 * Shape-only decoder for the 202 acknowledgment. Does NOT assert equality
 * with the submitted event_id (that is a request-specific postcondition
 * enforced by sendRuntimeErrorReport).
 */
export const runtimeErrorAckDecoder: ResponseDecoder<RuntimeErrorAcknowledgment> = {
  decode(value, ctx) {
    const dec = decodeObject<RuntimeErrorAcknowledgment>({
      required: {
        status: decodeEnum(["accepted"]),
        event_id: decodeString,
      },
    });
    return dec.decode(value, ctx);
  },
};

export const runtimeErrorContract: JsonContract<RuntimeErrorAcknowledgment> = {
  id: "diagnostics.runtimeError",
  method: "POST",
  pathPattern: "/diagnostics/runtime-error",
  responseKind: "json",
  decoder: runtimeErrorAckDecoder,
};
