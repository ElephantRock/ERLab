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
    throw new ApiError(res.status, body.detail || body.error || res.statusText);
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

export function sseUrl(path: string): string {
  const base = getBaseUrl() || window.location.origin;
  const key = getApiKey();
  const separator = path.includes("?") ? "&" : "?";
  const auth = key ? `${separator}api_key=${encodeURIComponent(key)}` : "";
  return `${base}${API_PREFIX}${path}${auth}`;
}
