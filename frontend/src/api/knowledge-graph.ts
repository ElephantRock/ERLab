/**
 * Knowledge Graph API client — BATCH-25/TASK-02
 *
 * Provides typed functions for the knowledge graph endpoints:
 *   GET /knowledge-graph/stats
 *   GET /knowledge-graph/entities?type=...&search=...&limit=100
 *   GET /knowledge-graph/entity/{id}
 *   GET /knowledge-graph/subgraph/{id}?depth=2
 */

import { apiFetchUnchecked } from "./client";

// ── Types ─────────────────────────────────────────────────────────

export interface GraphStats {
  entity_count: number;
  relationship_count: number;
  entity_types: Record<string, number>;
  relation_types: Record<string, number>;
}

export interface TruthInfo {
  confidence: number;
  frequency: number;
  source_count: number;
}

export interface GraphEntity {
  id: string;
  entity_type: string;
  name: string;
  aliases: string[];
  properties: Record<string, unknown>;
  truth: TruthInfo;
}

export interface GraphRelationship {
  source_id: string;
  target_id: string;
  relation_type: string;
  weight: number;
  evidence: string[];
  truth: TruthInfo;
}

export interface EntityDetail {
  entity: GraphEntity;
  relationships: GraphRelationship[];
}

export interface Subgraph {
  entities: GraphEntity[];
  relationships: GraphRelationship[];
}

export interface WorldModel {
  total_entities: number;
  total_relationships: number;
  entity_type_distribution: Record<string, number>;
  relationship_type_distribution: Record<string, number>;
  top_entities: GraphEntity[];
  strongest_relationships: GraphRelationship[];
}

// ── API Functions ─────────────────────────────────────────────────

/** GET /knowledge-graph/stats → graph statistics */
export function getGraphStats(): Promise<GraphStats> {
  return apiFetchUnchecked<GraphStats>("/knowledge-graph/stats");
}

/** GET /knowledge-graph/entities → entity list with optional filters (HB-02: max 100) */
export function getEntities(params?: {
  type?: string;
  search?: string;
  limit?: number;
}): Promise<GraphEntity[]> {
  const query = new URLSearchParams();
  if (params?.type) query.set("type", params.type);
  if (params?.search) query.set("search", params.search);
  if (params?.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiFetchUnchecked<GraphEntity[]>(`/knowledge-graph/entities${qs ? `?${qs}` : ""}`);
}

/** GET /knowledge-graph/entity/{id} → entity with relationships */
export function getEntity(id: string): Promise<EntityDetail> {
  return apiFetchUnchecked<EntityDetail>(`/knowledge-graph/entity/${encodeURIComponent(id)}`);
}

/** GET /knowledge-graph/subgraph/{id}?depth=N → connected subgraph */
export function getSubgraph(id: string, depth = 2): Promise<Subgraph> {
  return apiFetchUnchecked<Subgraph>(
    `/knowledge-graph/subgraph/${encodeURIComponent(id)}?depth=${depth}`,
  );
}

/** GET /knowledge-graph/world-model → high-level world model summary */
export function getWorldModel(): Promise<WorldModel> {
  return apiFetchUnchecked<WorldModel>("/knowledge-graph/world-model");
}
