import { apiFetchBlob } from "./client";
import { callContract } from "./contracts/common";
import { installPluginContract } from "./contracts/exports";
import { listPluginsContract } from "./contracts/f1-3a-reads";

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
  // F1.3a: migrated from apiFetchUnchecked to callContract with runtime decoder
  return callContract(listPluginsContract);
}

export function installPlugin(req: {
  name: string;
  version?: string;
  description?: string;
}): Promise<Plugin> {
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder.
  return callContract(installPluginContract, { body: req });
}
