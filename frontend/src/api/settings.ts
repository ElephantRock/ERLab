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
