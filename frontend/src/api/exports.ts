import { apiFetch } from "./client";

// --- Export ---

export interface ExportPdfRequest {
  idea_id: number;
}

export interface BulkExportRequest {
  idea_ids: number[];
  format?: "pdf" | "markdown";
}

export function exportPdf(req: ExportPdfRequest): Promise<Blob> {
  return apiFetch(`/export/pdf`, {
    method: "POST",
    body: JSON.stringify(req),
    headers: { Accept: "application/pdf" },
  }).then(() => {
    // apiFetch returns JSON, but we need a blob for file download
    // Use raw fetch for binary responses
    return rawExportFetch("/export/pdf", JSON.stringify(req));
  });
}

export function bulkExport(req: BulkExportRequest): Promise<Blob> {
  return rawExportFetch("/export/bulk", JSON.stringify(req));
}

async function rawExportFetch(path: string, body: string): Promise<Blob> {
  const { API_PREFIX } = await import("@/lib/constants");
  const baseUrl = localStorage.getItem("erock_api_url") || "";
  const key = localStorage.getItem("erock_api_key") || "";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (key) headers["X-API-Key"] = key;

  const res = await fetch(`${baseUrl}${API_PREFIX}${path}`, {
    method: "POST",
    headers,
    body,
  });

  if (!res.ok) {
    const errBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errBody.detail || errBody.error || res.statusText);
  }

  return res.blob();
}

// --- Plugins ---

export interface Plugin {
  name: string;
  version: string;
  description: string;
  enabled: boolean;
  metadata: Record<string, unknown>;
}

export interface PluginListResponse {
  plugins: Plugin[];
  total: number;
}

export function listPlugins(): Promise<PluginListResponse> {
  return apiFetch("/plugins/");
}

export function installPlugin(req: {
  name: string;
  version?: string;
  description?: string;
}): Promise<Plugin> {
  return apiFetch("/plugins/install", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
