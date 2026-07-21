/**
 * Memory API Client — BATCH-19/TASK-01
 *
 * Typed functions for all 3 memory endpoints.
 * Endpoint shapes from backend/api/routes/memory.py:
 *   GET  /memory/stats       → {total_memories, by_type}
 *   GET  /memory/recall      → {query, results: [{content, type, confidence, created_at}]}
 *   DELETE /memory/{id}      → {status, entry_id}
 *
 * NOTE: There is NO /memories list endpoint. All browsing uses /recall
 * with a broad query (e.g., "*"). Memory types include: semantic, episodic, procedural.
 */

import { apiFetchUnchecked } from "./client";

// ── Types ────────────────────────────────────────────────────────

export type MemoryType = "semantic" | "episodic" | "procedural";

export interface MemoryStats {
  total_memories: number;
  by_type: Record<string, number>;
}

export interface MemoryRecallResult {
  content: string;
  type: string;
  confidence: number;
  created_at: string;
}

export interface MemoryRecallResponse {
  query: string;
  results: MemoryRecallResult[];
}

export interface MemoryDeleteResponse {
  status: string;
  entry_id: string;
}

// ── API Functions ────────────────────────────────────────────────

export function getMemoryStats(): Promise<MemoryStats> {
  return apiFetchUnchecked<MemoryStats>("/memory/stats");
}

export function recallMemories(
  query: string,
  params?: { memory_type?: string; top_k?: number },
): Promise<MemoryRecallResponse> {
  const searchParams = new URLSearchParams({ query });
  if (params?.memory_type) {
    searchParams.set("memory_type", params.memory_type);
  }
  if (params?.top_k !== undefined) {
    searchParams.set("top_k", String(params.top_k));
  }
  return apiFetchUnchecked<MemoryRecallResponse>(`/memory/recall?${searchParams.toString()}`);
}

export function deleteMemory(id: string): Promise<MemoryDeleteResponse> {
  return apiFetchUnchecked<MemoryDeleteResponse>(`/memory/${id}`, {
    method: "DELETE",
  });
}
