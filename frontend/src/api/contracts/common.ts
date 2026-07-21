/**
 * F1.1 — Canonical endpoint-contract primitives.
 *
 * The transport layer (apiFetch in src/api/client.ts) owns HTTP concerns:
 * auth headers, method, body, status handling, JSON/text/empty-body
 * transport, normalized network/HTTP errors. It MUST NOT claim that an
 * arbitrary JSON payload satisfies a domain interface.
 *
 * This module layers on top of apiFetch to add runtime response validation.
 * The flow is:
 *
 *   page/component
 *     → typed endpoint client  (clients/*-client.ts)
 *     → apiFetch transport     (client.ts)
 *     → runtime decoder        (here + contracts/*)
 *     → validated domain value
 *
 * A decoder failure is NOT an empty result. It surfaces as ApiContractError,
 * which query layers (useQuery/useResource) translate into the failed UI
 * state. This keeps "backend returned malformed payload" distinguishable
 * from "backend returned an empty successful list".
 *
 * No external schema library is used (none was a dependency before F1.1).
 * Decoders are small and explicit per the F1.1 directive.
 */

import { apiFetch } from "@/api/client";

// ── Contract failure ─────────────────────────────────────────────────

/**
 * Bounded contract-failure vocabulary. A response-contract failure is not
 * an empty result and not a transport error — it means the HTTP request
 * succeeded (2xx) but the payload did not match the declared contract.
 */
export type ContractFailureCode =
  | "api_response_contract_mismatch"
  | "api_response_empty_when_payload_expected"
  | "api_response_payload_when_empty_expected";

/**
 * Raised when a 2xx response's payload fails the decoder, or when the
 * empty-body policy is violated (payload on a void endpoint, or empty body
 * on an endpoint that requires a payload).
 *
 * Carries safe diagnostic context — never raw response bodies, which may
 * contain sensitive research content.
 */
export class ApiContractError extends Error {
  constructor(
    public readonly code: ContractFailureCode,
    public readonly endpointId: string,
    public readonly detail: string,
    public readonly httpStatus: number,
    public readonly correlationId?: string,
  ) {
    super(`${code} on ${endpointId}: ${detail}`);
    this.name = "ApiContractError";
  }
}

// ── Decoder interface ────────────────────────────────────────────────

/**
 * A runtime decoder from `unknown` (the raw JSON) to a validated domain
 * value `T`. Throws `ApiContractError` (or any Error, which the caller
 * wraps) on mismatch — never returns a silently-coerced value.
 *
 * Material fields (IDs, status, counts that drive decisions) are validated
 * strictly. Unknown extra fields are permitted for forward compatibility
 * while consumed fields are validated — exact-object rejection is not the
 * default.
 */
export interface ResponseDecoder<T> {
  decode(value: unknown, ctx: DecodeContext): T;
}

export interface DecodeContext {
  readonly endpointId: string;
}

// ── Endpoint contract ────────────────────────────────────────────────

export type EmptyBodyPolicy = "forbidden" | "allowed" | "required";

export interface EndpointContract<TResponse> {
  /** Stable identifier for diagnostics, e.g. "gaps.getGap". */
  readonly id: string;
  readonly method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  /** Path template; use `buildPath` to substitute params. */
  readonly pathPattern: string;
  /** Status codes that count as success for this endpoint. Default [200]. */
  readonly successStatuses?: readonly number[];
  /**
   * Empty-body policy:
   *   "forbidden" — a payload is required; 204/empty body is a contract error
   *   "allowed"   — payload or empty body are both valid (decoder gets unknown)
   *   "required"  — the endpoint returns no body; decode is skipped, returns void
   */
  readonly emptyBody: EmptyBodyPolicy;
  /** Decoder for the response payload. Required unless emptyBody === "required". */
  readonly decodeResponse?: ResponseDecoder<TResponse>;
}

// ── Primitive decoders ───────────────────────────────────────────────

/** Assert a value is a string. */
export const decodeString: ResponseDecoder<string> = {
  decode(value, ctx) {
    if (typeof value !== "string") {
      throw new ApiContractError(
        "api_response_contract_mismatch",
        ctx.endpointId,
        `expected string, got ${typeof value}`,
        200,
      );
    }
    return value;
  },
};

/** Assert a value is a number (not NaN). */
export const decodeNumber: ResponseDecoder<number> = {
  decode(value, ctx) {
    if (typeof value !== "number" || Number.isNaN(value)) {
      throw new ApiContractError(
        "api_response_contract_mismatch",
        ctx.endpointId,
        `expected number, got ${typeof value}${value === null ? " (null)" : ""}`,
        200,
      );
    }
    return value;
  },
};

/** Assert a value is a boolean. */
export const decodeBoolean: ResponseDecoder<boolean> = {
  decode(value, ctx) {
    if (typeof value !== "boolean") {
      throw new ApiContractError(
        "api_response_contract_mismatch",
        ctx.endpointId,
        `expected boolean, got ${typeof value}`,
        200,
      );
    }
    return value;
  },
};

/**
 * Build a decoder for an object with required + optional typed fields.
 * Unknown extra fields are preserved (forward compatibility) — only the
 * declared fields are validated. Material fields passed to `required` are
 * strictly checked; fields passed to `optional` must be present-and-correct
 * only when the backend includes them.
 */
export function decodeObject<T extends object>(fields: {
  required?: { [K in keyof T]?: ResponseDecoder<T[K]> };
  // Optional fields accept a decoder of any concrete type; the decoded
  // value is merged into the output object (typed via T). The decoder
  // validates the field's shape when the backend includes it.
  optional?: Record<string, ResponseDecoder<unknown>>;
}): ResponseDecoder<T> {
  return {
    decode(value, ctx) {
      if (typeof value !== "object" || value === null || Array.isArray(value)) {
        throw new ApiContractError(
          "api_response_contract_mismatch",
          ctx.endpointId,
          `expected object, got ${value === null ? "null" : Array.isArray(value) ? "array" : typeof value}`,
          200,
        );
      }
      const obj = value as Record<string, unknown>;
      const out: Record<string, unknown> = { ...obj };
      if (fields.required) {
        for (const key of Object.keys(fields.required) as (keyof T)[]) {
          const dec = fields.required[key]!;
          if (!(key in obj) || obj[key as string] === undefined) {
            throw new ApiContractError(
              "api_response_contract_mismatch",
              ctx.endpointId,
              `required field ${String(key)} missing or undefined`,
              200,
            );
          }
          out[key as string] = dec.decode(obj[key as string], ctx);
        }
      }
      if (fields.optional) {
        for (const key of Object.keys(fields.optional)) {
          // Skip absent, undefined, AND null optionals — a backend `null`
          // for an optional field means "not present" (e.g. novelty: null
          // when no novelty review was produced). Decoding null as the
          // field's type would fail; preserving null keeps the value
          // truthful for consumers that check for it.
          if (key in obj && obj[key] !== undefined && obj[key] !== null) {
            out[key] = fields.optional[key]!.decode(obj[key], ctx);
          }
        }
      }
      return out as unknown as T;
    },
  };
}

/** Decoder for a homogeneous array. */
export function decodeArray<T>(itemDecoder: ResponseDecoder<T>): ResponseDecoder<T[]> {
  return {
    decode(value, ctx) {
      if (!Array.isArray(value)) {
        throw new ApiContractError(
          "api_response_contract_mismatch",
          ctx.endpointId,
          `expected array, got ${typeof value}`,
          200,
        );
      }
      return value.map((item, i) => {
        try {
          return itemDecoder.decode(item, ctx);
        } catch (e) {
          if (e instanceof ApiContractError) {
            throw new ApiContractError(e.code, e.endpointId, `${e.detail} (at index ${i})`, e.httpStatus, e.correlationId);
          }
          throw e;
        }
      });
    },
  };
}

/**
 * Decoder for a string that must be one of a closed vocabulary.
 * Used for status fields that drive product decisions.
 */
export function decodeEnum<T extends string>(values: readonly T[]): ResponseDecoder<T> {
  const set = new Set(values as readonly string[]);
  return {
    decode(value, ctx) {
      if (typeof value !== "string" || !set.has(value)) {
        throw new ApiContractError(
          "api_response_contract_mismatch",
          ctx.endpointId,
          `expected one of [${values.join(", ")}], got ${JSON.stringify(value)}`,
          200,
        );
      }
      return value as T;
    },
  };
}

/**
 * Decoder for `Record<string, string>` — an object whose values must all be
 * strings. Empty object `{}` is valid (no entries). Used for assignment
 * maps, override maps, and similar string-valued dictionaries.
 */
export const decodeStringRecord: ResponseDecoder<Record<string, string>> = {
  decode(value, ctx) {
    if (typeof value !== "object" || value === null || Array.isArray(value)) {
      throw new ApiContractError(
        "api_response_contract_mismatch",
        ctx.endpointId,
        `expected object (string record), got ${value === null ? "null" : Array.isArray(value) ? "array" : typeof value}`,
        200,
      );
    }
    const obj = value as Record<string, unknown>;
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(obj)) {
      if (typeof v !== "string") {
        throw new ApiContractError(
          "api_response_contract_mismatch",
          ctx.endpointId,
          `string record value for key ${JSON.stringify(k)} expected string, got ${typeof v}`,
          200,
        );
      }
      out[k] = v;
    }
    return out;
  },
};

// ── Path helper ──────────────────────────────────────────────────────

/**
 * Substitute `{param}` placeholders in a path pattern.
 * Params are stringified (route IDs may be number or string per backend).
 */
export function buildPath(pattern: string, params: Record<string, string | number>): string {
  return pattern.replace(/\{(\w+)\}/g, (_, key: string) => {
    if (!(key in params)) {
      throw new Error(`buildPath: missing param ${key} for pattern ${pattern}`);
    }
    return String(params[key]);
  });
}

/**
 * Append query params, dropping undefined/null/empty values.
 * Values are stringified; arrays use repeated keys.
 */
export function withQuery(path: string, params: Record<string, unknown>): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const v of value) sp.append(key, String(v));
    } else {
      sp.append(key, String(value));
    }
  }
  const qs = sp.toString();
  return qs ? `${path}?${qs}` : path;
}

// ── Contract executor ────────────────────────────────────────────────

/**
 * Execute an endpoint contract: call apiFetch, then validate the response
 * against the declared decoder + empty-body policy.
 *
 * - Transport errors (non-2xx, network failure) propagate as `ApiError`
 *   from apiFetch — unchanged.
 * - 2xx + decoder failure raises `ApiContractError` — the caller (query
 *   layer) treats this as a failed query state.
 * - `emptyBody: "required"` endpoints return `void` (no decoder run).
 *
 * `correlationId` is extracted from the response headers if present
 * (X-Request-ID) and attached to contract errors for diagnostics.
 */
export async function callContract<TResponse>(
  contract: EndpointContract<TResponse>,
  options: {
    params?: Record<string, string | number>;
    query?: Record<string, unknown>;
    body?: unknown;
    signal?: AbortSignal;
    extraHeaders?: Record<string, string>;
  } = {},
): Promise<TResponse> {
  const path = withQuery(
    options.params ? buildPath(contract.pathPattern, options.params) : contract.pathPattern,
    options.query ?? {},
  );

  const init: RequestInit = {
    method: contract.method,
    signal: options.signal,
    headers: options.extraHeaders,
  };
  if (options.body !== undefined && contract.method !== "GET") {
    init.body = JSON.stringify(options.body);
  }

  // apiFetch returns `T` but we deliberately take `unknown` here — the
  // transport's generic T is an unchecked assertion we no longer trust.
  // The decoder is what makes the value usable.
  const raw: unknown = await (apiFetch as unknown as (p: string, o?: RequestInit) => Promise<unknown>)(path, init);

  if (contract.emptyBody === "required") {
    if (raw !== undefined && raw !== null) {
      throw new ApiContractError(
        "api_response_payload_when_empty_expected",
        contract.id,
        `endpoint declared emptyBody:"required" but received a payload`,
        200,
      );
    }
    return undefined as TResponse;
  }

  if (raw === undefined || raw === null) {
    if (contract.emptyBody === "forbidden") {
      throw new ApiContractError(
        "api_response_empty_when_payload_expected",
        contract.id,
        `endpoint declared emptyBody:"forbidden" but received an empty body`,
        200,
      );
    }
    // emptyBody: "allowed" — return null/undefined as-is, typed via TResponse
    return raw as TResponse;
  }

  if (!contract.decodeResponse) {
    // No decoder declared but payload present and emptyBody !== "required".
    // This is a misconfigured contract; fail loud rather than trusting raw.
    throw new ApiContractError(
      "api_response_contract_mismatch",
      contract.id,
      `endpoint has no decodeResponse but received a payload (misconfigured contract)`,
      200,
    );
  }

  return contract.decodeResponse.decode(raw, { endpointId: contract.id });
}

/**
 * Extract a request-correlation identifier from a fetch Response, if the
 * backend provides one (X-Request-ID). Currently unused by apiFetch (which
 * doesn't expose headers) — retained here for F1.6 error observability when
 * the transport is extended to surface response headers.
 */
export function extractCorrelationId(headers: Headers): string | undefined {
  return headers.get("X-Request-ID") ?? headers.get("x-request-id") ?? undefined;
}
