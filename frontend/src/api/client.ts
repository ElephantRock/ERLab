import { API_PREFIX } from "@/lib/constants";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

function getBaseUrl(): string {
  return localStorage.getItem("erock_api_url") || "";
}

function getApiKey(): string {
  return localStorage.getItem("erock_api_key") || "";
}

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> | undefined),
  };
  const key = getApiKey();
  if (key) {
    headers["X-API-Key"] = key;
  }

  const res = await fetch(`${getBaseUrl()}${API_PREFIX}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    // Backend returns {detail: "..."} or {error: {message: "...", code: "..."}} or {error: "string"}
    const message =
      body.detail ||
      (body.error && typeof body.error === 'object' ? body.error.message : null) ||
      (typeof body.error === 'string' ? body.error : null) ||
      res.statusText;
    throw new ApiError(res.status, message);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

/** Test backend connectivity via /health endpoint. */
export async function testConnection(baseUrl?: string): Promise<{ ok: true; version: string } | { ok: false; error: string }> {
  try {
    const base = baseUrl ?? getBaseUrl();
    const res = await fetch(`${base}/health`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) {
      return { ok: false, error: `HTTP ${res.status}` };
    }
    const data = await res.json();
    return { ok: true, version: data.version ?? "unknown" };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

/** Detailed status response from /api/v1/status/detailed. */
export interface DetailedStatus {
  version: string;
  provider: string;
  db_status: string;
}

/** Fetch detailed status from the backend. */
export async function getDetailedStatus(): Promise<DetailedStatus> {
  return apiFetch<DetailedStatus>("/status/detailed");
}

/** Fetch-based SSE connection with Authorization header (BATCH-31, HB-01).
 *  Replaces the legacy sseUrl() which put API keys in query params.
 */
export function sseFetch(
  path: string,
  callbacks: {
    onEvent: (data: string) => void;
    onOpen?: () => void;
    onError?: (error: Error) => void;
  },
): AbortController {
  const controller = new AbortController();
  const headers: Record<string, string> = {};
  const key = getApiKey();
  if (key) {
    headers["X-API-Key"] = key;
  }
  const base = getBaseUrl() || window.location.origin;
  const url = `${base}${API_PREFIX}${path}`;

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
          for (const line of part.split("\n")) {
            if (line.startsWith("data: ")) {
              callbacks.onEvent(line.slice(6));
            }
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError" && callbacks.onError) {
        callbacks.onError(err instanceof Error ? err : new Error(String(err)));
      }
    }
  })();

  return controller;
}
