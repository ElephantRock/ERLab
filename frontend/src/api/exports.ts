import { apiFetchUnchecked, apiFetchBlob } from "./client";

// --- Export ---

export interface ExportPdfRequest {
  idea_id: number;
}

export interface BulkExportRequest {
  idea_ids: number[];
  format?: "pdf" | "markdown";
}

/** Export a single idea as PDF. Returns a Blob for download. */
export function exportPdf(req: ExportPdfRequest): Promise<Blob> {
  return apiFetchBlob("/export/pdf", {
    method: "POST",
    body: JSON.stringify(req),
    headers: { Accept: "application/pdf" },
  });
}

/** Bulk export multiple ideas. Returns a Blob (zip or markdown). */
export function bulkExport(req: BulkExportRequest): Promise<Blob> {
  return apiFetchBlob("/export/bulk", {
    method: "POST",
    body: JSON.stringify(req),
  });
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
  return apiFetchUnchecked("/plugins/");
}

export function installPlugin(req: {
  name: string;
  version?: string;
  description?: string;
}): Promise<Plugin> {
  return apiFetchUnchecked("/plugins/install", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
