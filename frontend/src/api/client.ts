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

export function sseUrl(path: string): string {
  const base = getBaseUrl() || window.location.origin;
  const key = getApiKey();
  const separator = path.includes("?") ? "&" : "?";
  const auth = key ? `${separator}api_key=${encodeURIComponent(key)}` : "";
  return `${base}${API_PREFIX}${path}${auth}`;
}
