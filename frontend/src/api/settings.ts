import { apiFetch } from "./client";

// ── Catalog (GET /settings/catalog) ──────────────────────────────

export interface ModelCapabilities {
  json_mode: boolean;
  tools: boolean;
  vision: boolean;
  thinking: boolean;
}

export interface ModelMeasuredStats {
  total_calls: number;
  reliability: number;
  json_reliability: number;
}

export interface CatalogModel {
  model_id: string;
  display_name: string;
  provider_type: string;
  endpoint_url: string;
  parameter_count: string;
  context_length: number;
  context_label: string;
  quantization: string;
  size_gb: number;
  capabilities: ModelCapabilities;
  is_loaded: boolean;
  health_status: string;
  measured: ModelMeasuredStats | null;
}

export interface GpuInfo {
  name: string;
  vram_total_gb: number;
  vram_available_gb: number;
}

export interface CatalogResponse {
  models: CatalogModel[];
  total: number;
  gpu: GpuInfo | null;
  error?: string;
}

// ── Assignments (GET /settings/assignments) ──────────────────────

export interface StageAssignment {
  model_id: string;
  parameter_count: string;
  context_label: string;
  is_loaded: boolean;
  quantization: string;
}

export interface AssignmentsResponse {
  assignments: Record<string, StageAssignment>;
  total_stages: number;
  error?: string;
}

// ── API Functions ────────────────────────────────────────────────

export function getCatalog(): Promise<CatalogResponse> {
  return apiFetch<CatalogResponse>("/settings/catalog");
}

export function getAssignments(): Promise<AssignmentsResponse> {
  return apiFetch<AssignmentsResponse>("/settings/assignments");
}

// ── Stage Metadata (GET /settings/stages) ──────────────────────

export interface StageInfo {
  name: string;
  label: string;
  category: "thinking" | "generation" | "passthrough";
  needs_llm: boolean;
}

export interface StagesResponse {
  stages: StageInfo[];
  total: number;
}

export function getStages(): Promise<StagesResponse> {
  return apiFetch<StagesResponse>("/settings/stages");
}

// ── Certification (GET /settings/certification) ─────────────────

export interface CertificationEntry {
  model_id: string;
  provider: string;
  status: string;
  allowed_stages: Record<string, string>;
}

export interface CertificationResponse {
  certifications: CertificationEntry[];
  total: number;
  error?: string;
}

export function getCertification(): Promise<CertificationResponse> {
  return apiFetch<CertificationResponse>("/settings/certification");
}

// ── Model Overrides (GET/PUT/DELETE /settings/overrides) ───────

export interface OverrideWarning {
  code: string;
  stage: string;
  model_id: string;
  message: string;
}

export interface OverridesResponse {
  overrides: Record<string, string>;
  total: number;
}

export interface OverrideUpdateResponse {
  overrides: Record<string, string>;
  warnings: OverrideWarning[];
  message?: string;
  dry_run?: boolean;
}

export interface OverrideValidateResponse {
  valid: boolean;
  overrides: Record<string, string>;
  warnings: OverrideWarning[];
}

export function getOverrides(): Promise<OverridesResponse> {
  return apiFetch<OverridesResponse>("/settings/overrides");
}

export function updateOverrides(
  body: Record<string, string>,
  dryRun?: boolean,
): Promise<OverrideUpdateResponse> {
  const qs = dryRun ? "?dry_run=true" : "";
  return apiFetch<OverrideUpdateResponse>(`/settings/overrides${qs}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function validateOverrides(
  body: Record<string, string>,
): Promise<OverrideValidateResponse> {
  return apiFetch<OverrideValidateResponse>("/settings/overrides/validate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function removeOverride(stage: string): Promise<{ message: string; overrides: Record<string, string> }> {
  return apiFetch(`/settings/overrides/${stage}`, { method: "DELETE" });
}

export function clearAllOverrides(): Promise<{ message: string; overrides: Record<string, string> }> {
  return apiFetch("/settings/overrides", { method: "DELETE" });
}
