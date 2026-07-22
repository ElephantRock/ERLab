import { API_PREFIX } from "@/lib/constants";
import { callContract } from "./contracts/common";
import { getDetailedStatusContract } from "./contracts/f1-3a-reads";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

// ── Single source of truth for API URL, API key, and JWT token ───
// All localStorage reads for erock_api_url / erock_api_key / erock_jwt_token
// go through these functions. No other module should read these keys
// directly.

export function getApiUrl(): string {
  return localStorage.getItem("erock_api_url") || "";
}

export function getApiKey(): string {
  return localStorage.getItem("erock_api_key") || "";
}

export function getJwtToken(): string {
  return localStorage.getItem("erock_jwt_token") || "";
}

/** Build a full URL from a path, using the configured base URL. */
export function buildUrl(path: string): string {
  return `${getApiUrl()}${API_PREFIX}${path}`;
}

/** Build auth headers with API key and JWT token if present.
 *
 * Merges (in priority order — last wins for overlapping keys):
 * 1. API key via X-API-Key header
 * 2. JWT token via Authorization: Bearer header
 * 3. Caller-provided extra headers (can override either)
 */
export function buildAuthHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  const key = getApiKey();
  if (key && !("X-API-Key" in headers)) {
    headers["X-API-Key"] = key;
  }
  const token = getJwtToken();
  if (token && !("Authorization" in headers)) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

// ── Transport primitives (F1.1a seal) ───────────────────────────────
//
// The transport owns ONLY network concerns: auth headers, HTTP method,
// status handling, JSON/empty-body transport, normalized errors. It must
// never fabricate a generic domain value.
//
// apiFetchJson returns `unknown` — the caller (contract layer or legacy
// apiFetchUnchecked<T>) is responsible for validation.
// apiFetchVoid is for endpoints that genuinely return no body.
// apiFetchUnchecked<T> is a legacy adapter preserved for the ~78 pre-contract call
// sites; it delegates to apiFetchJson and casts the result to T. New code
// should use the contract layer (contracts/common.ts callContract) or
// apiFetchJson directly.

async function doFetch(path: string, options?: RequestInit): Promise<Response> {
  const headers = buildAuthHeaders({
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> | undefined),
  });
  return fetch(buildUrl(path), { ...options, headers });
}

async function handleHttpError(res: Response): Promise<never> {
  const body = await res.json().catch(() => ({ detail: res.statusText }));
  const message =
    body.detail ||
    (body.error && typeof body.error === "object" ? body.error.message : null) ||
    (typeof body.error === "string" ? body.error : null) ||
    res.statusText;
  throw new ApiError(res.status, message);
}

/** Transport for JSON-returning endpoints. Returns `unknown` — NOT a typed
 *  domain value. The caller must validate (contract layer) or explicitly
 *  cast (legacy apiFetchUnchecked<T>). Throws ApiError on non-2xx. Throws on 204
 *  (a JSON endpoint receiving 204 is a contract violation at this layer).
 */
export async function apiFetchJson(path: string, options?: RequestInit): Promise<unknown> {
  const res = await doFetch(path, options);
  if (!res.ok) return handleHttpError(res);
  if (res.status === 204) {
    throw new ApiError(204, "expected JSON response but received 204 No Content");
  }
  return res.json();
}

/** Transport for void endpoints (no response body). Throws ApiError on
 *  non-2xx. Accepts 200-with-body or 204-no-body. */
export async function apiFetchVoid(path: string, options?: RequestInit): Promise<void> {
  const res = await doFetch(path, options);
  if (!res.ok) return handleHttpError(res);
  // 204 or any 2xx is valid for void; body is discarded
}

/** UNCHECKED legacy generic fetch — preserved for pre-contract call sites.
 *
 * **WARNING**: This function casts arbitrary JSON to T WITHOUT runtime
 * validation. It is an explicitly unsafe adapter. The caller count is
 * frozen in `api-unchecked-budget.json` and enforced by
 * `scripts/check-api-unchecked-budget.cjs` in CI. The budget may only
 * DECREASE — new callers must use the contract layer (callContract) or
 * apiFetchJson with an explicit decoder.
 *
 * Delegates to apiFetchJson and casts the result to T.
 */
export async function apiFetchUnchecked<T>(path: string, options?: RequestInit): Promise<T> {
  return (await apiFetchJson(path, options)) as T;
}

// ── Binary/blob fetch ───────────────────────────────────────────

/** Fetch a binary response (PDF, zip, etc.) with auth headers.
 *  Returns a Blob for download or further processing.
 */
export async function apiFetchBlob(path: string, options?: RequestInit): Promise<Blob> {
  const headers = buildAuthHeaders({
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> | undefined),
  });

  const res = await fetch(buildUrl(path), {
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const message =
      body.detail ||
      (body.error && typeof body.error === 'object' ? body.error.message : null) ||
      (typeof body.error === 'string' ? body.error : null) ||
      res.statusText;
    throw new ApiError(res.status, message);
  }

  return res.blob();
}

// ── FormData fetch (multipart uploads) ──────────────────────────

/** Upload FormData with auth headers. Does NOT set Content-Type — the
 *  browser sets the correct multipart boundary automatically.
 */
export async function apiFetchFormData<T>(path: string, formData: FormData): Promise<T> {
  const headers = buildAuthHeaders();

  const res = await fetch(buildUrl(path), {
    method: "POST",
    headers,
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const message =
      body.detail ||
      (body.error && typeof body.error === 'object' ? body.error.message : null) ||
      (typeof body.error === 'string' ? body.error : null) ||
      res.statusText;
    throw new ApiError(res.status, message);
  }

  return res.json();
}

// ── Connection test ─────────────────────────────────────────────

/** Test backend connectivity via /health endpoint. */
export async function testConnection(baseUrl?: string): Promise<{ ok: true; version: string } | { ok: false; error: string }> {
  try {
    const base = baseUrl ?? getApiUrl();
    // Try /health first (root-level), fall back to /api/v1/status
    // Both are proxied by Vite in dev mode
    let res = await fetch(`${base}/health`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    }).catch(() => null);

    if (!res || !res.ok) {
      // Fallback: use API status endpoint (always under /api proxy)
      res = await fetch(`${base}${API_PREFIX}/status`, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      });
    }

    if (!res.ok) {
      return { ok: false, error: `HTTP ${res.status}` };
    }
    const data = await res.json();
    return { ok: true, version: data.version ?? "unknown" };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

// ── Detailed status ─────────────────────────────────────────────

/** Detailed status response from /api/v1/status/detailed. */
export interface DetailedStatus {
  version: string;
  provider: string;
  db_status: string;
}

/** Fetch detailed status from the backend. */
export async function getDetailedStatus(): Promise<DetailedStatus> {
  // F1.3a: migrated from apiFetchUnchecked to callContract with runtime decoder
  return callContract(getDetailedStatusContract);
}

// ── SSE with durable replay ─────────────────────────────────────

/** SSE callback interface with reconnect support. */
export interface SseCallbacks {
  onEvent: (data: string) => void;
  /** Called with the event ID for each event that has one. Used for Last-Event-ID tracking. */
  onEventId?: (id: string) => void;
  onOpen?: () => void;
  onError?: (error: Error) => void;
  /** Called when the connection drops. If provided, enables auto-reconnect
   *  with Last-Event-ID resume. Return false to prevent reconnect. */
  shouldReconnect?: () => boolean;
}

/** SSE connection with auth headers and Last-Event-ID replay support.
 *
 * Phase 6: Added Last-Event-ID header for durable replay. When a connection
 * drops, the client can reconnect with the last event ID received, and the
 * backend replays missed events from the run_events table.
 */
export function sseFetch(
  path: string,
  callbacks: SseCallbacks,
  options?: { lastEventId?: string; signal?: AbortSignal },
): AbortController {
  const controller = new AbortController();
  const headers: Record<string, string> = {};
  const key = getApiKey();
  if (key) {
    headers["X-API-Key"] = key;
  }
  const token = getJwtToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  // Last-Event-ID for durable replay
  const lastEventId = options?.lastEventId;
  if (lastEventId) {
    headers["Last-Event-ID"] = lastEventId;
  }

  const base = getApiUrl() || window.location.origin;
  const url = `${base}${API_PREFIX}${path}`;

  // Merge external abort signal with our controller
  if (options?.signal) {
    options.signal.addEventListener("abort", () => controller.abort());
  }

  (async () => {
    try {
      const response = await fetch(url, { headers, signal: controller.signal });
      if (!response.ok) {
        throw new Error(`SSE connection failed: HTTP ${response.status}`);
      }
      callbacks.onOpen?.();
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        // SSE events are separated by blank lines (\n\n)
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          let eventId: string | null = null;
          for (const line of part.split("\n")) {
            if (line.startsWith("id: ")) {
              eventId = line.slice(4).trim();
            }
            if (line.startsWith("data: ")) {
              callbacks.onEvent(line.slice(6));
            }
          }
          if (eventId) {
            callbacks.onEventId?.(eventId);
          }
        }
      }

      // Connection ended normally — check for reconnect
      if (callbacks.shouldReconnect?.()) {
        callbacks.onError?.(new Error("SSE connection ended, attempting reconnect"));
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError" && callbacks.onError) {
        callbacks.onError(err instanceof Error ? err : new Error(String(err)));
      }
    }
  })();

  return controller;
}
