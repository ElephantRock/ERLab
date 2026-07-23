import { describe, it, expect, beforeEach, vi } from "vitest";
import { getMemoryStats, recallMemories, deleteMemory } from "@/api/memory";
import type { MemoryStats, MemoryRecallResponse, MemoryDeleteResponse } from "@/api/memory";
import { apiFetchJson } from "@/api/client";

// F1.7a: all three memory functions now route through callContract → apiFetchJson.
vi.mock("@/api/client", () => ({
  apiFetchJson: vi.fn(),
  apiFetchUnchecked: vi.fn(),
}));

const mockApiFetchJson = vi.mocked(apiFetchJson);

describe("BATCH-19/TASK-01: Memory API Client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── TEST-19-01-01: getMemoryStats() calls /memory/stats ────────
  it("TEST-19-01-01: getMemoryStats() calls /memory/stats", async () => {
    const expected: MemoryStats = {
      total_memories: 42,
      by_type: { semantic: 20, episodic: 15, procedural: 7 },
    };
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await getMemoryStats();

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/memory/stats",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual(expected);
    expect(result.total_memories).toBe(42);
    expect(result.by_type.semantic).toBe(20);
  });

  // ── TEST-19-01-02: recallMemories(query) sends query param ─────
  it("TEST-19-01-02: recallMemories(query) sends query param", async () => {
    const expected: MemoryRecallResponse = {
      query: "transformer",
      results: [
        {
          content: "RAG+reranking improves retrieval by 15%",
          type: "semantic",
          confidence: 0.85,
          created_at: "2026-05-01T12:00:00",
        },
      ],
    };
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await recallMemories("transformer");

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      expect.stringContaining("/memory/recall?query=transformer"),
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual(expected);
    expect(result.results).toHaveLength(1);
    expect(result.results[0].type).toBe("semantic");
  });

  // ── TEST-19-01-03: deleteMemory(id) calls DELETE /memory/{id} ──
  it("TEST-19-01-03: deleteMemory(id) calls DELETE /memory/{id}", async () => {
    const expected: MemoryDeleteResponse = {
      status: "deleted",
      entry_id: "mem_abc123",
    };
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await deleteMemory("mem_abc123");

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/memory/mem_abc123",
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(result).toEqual(expected);
    expect(result.status).toBe("deleted");
    expect(result.entry_id).toBe("mem_abc123");
  });
});
