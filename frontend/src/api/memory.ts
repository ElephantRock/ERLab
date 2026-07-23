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
 *
 * F1.7a: all three callers migrated from apiFetchUnchecked to callContract
 * with runtime decoders.
 */

import {
  callContract,
  decodeArray,
  decodeNumber,
  decodeNumberRecord,
  decodeObject,
  decodeString,
  type JsonContract,
} from "./contracts/common";

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

// ── Contracts (F1.7a) ────────────────────────────────────────────

// Material fields: total_memories (count display) + by_type (per-type counts
// for the stats breakdown). by_type is Record<string, number> — every value
// is a count.
const getMemoryStatsContract: JsonContract<MemoryStats> = {
  id: "memory.getMemoryStats",
  method: "GET",
  pathPattern: "/memory/stats",
  responseKind: "json",
  decoder: decodeObject<MemoryStats>({
    required: {
      total_memories: decodeNumber,
      by_type: decodeNumberRecord,
    },
  }),
};

// Material fields per result: content (display), type (badge), confidence
// (display), created_at (timestamp). The query echo is required.
const memoryRecallResultDecoder = decodeObject<MemoryRecallResult>({
  required: {
    content: decodeString,
    type: decodeString,
    confidence: decodeNumber,
    created_at: decodeString,
  },
});

const recallMemoriesContract: JsonContract<MemoryRecallResponse> = {
  id: "memory.recallMemories",
  method: "GET",
  pathPattern: "/memory/recall",
  responseKind: "json",
  decoder: decodeObject<MemoryRecallResponse>({
    required: {
      query: decodeString,
      results: decodeArray(memoryRecallResultDecoder),
    },
  }),
};

// DELETE returns { status: "deleted", entry_id: <echoed id> }.
const deleteMemoryContract: JsonContract<MemoryDeleteResponse> = {
  id: "memory.deleteMemory",
  method: "DELETE",
  pathPattern: "/memory/{id}",
  responseKind: "json",
  decoder: decodeObject<MemoryDeleteResponse>({
    required: {
      status: decodeString,
      entry_id: decodeString,
    },
  }),
};

// ── API Functions ────────────────────────────────────────────────

export function getMemoryStats(): Promise<MemoryStats> {
  return callContract(getMemoryStatsContract);
}

export function recallMemories(
  query: string,
  params?: { memory_type?: string; top_k?: number },
): Promise<MemoryRecallResponse> {
  return callContract(recallMemoriesContract, {
    query: { query, memory_type: params?.memory_type, top_k: params?.top_k },
  });
}

export function deleteMemory(id: string): Promise<MemoryDeleteResponse> {
  return callContract(deleteMemoryContract, { params: { id } });
}
