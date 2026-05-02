import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryCard } from "@/components/memory/memory-card";
import { MemoryStats } from "@/components/memory/memory-stats";
import type { MemoryRecallResult } from "@/api/memory";

const sampleMemory: MemoryRecallResult = {
  content: "RAG+reranking improves retrieval by 15% across benchmarks.",
  type: "semantic",
  confidence: 0.85,
  created_at: "2026-05-01T12:00:00",
};

describe("BATCH-19/TASK-01: Memory Components", () => {
  // ── TEST-19-01-04: MemoryCard renders content, type badge, confidence
  it("TEST-19-01-04: MemoryCard renders content, type badge, confidence", () => {
    render(<MemoryCard memory={sampleMemory} />);

    expect(screen.getByTestId("memory-card")).toBeInTheDocument();
    expect(screen.getByText(/RAG\+reranking improves retrieval/)).toBeInTheDocument();
    expect(screen.getByText("semantic")).toBeInTheDocument();
    expect(screen.getByText("85%")).toBeInTheDocument();
    expect(screen.getByTestId("confidence-bar")).toBeTruthy();
  });

  // ── TEST-19-01-05: MemoryStats renders total and per-type counts
  it("TEST-19-01-05: MemoryStats renders total and per-type counts", () => {
    const stats = {
      total_memories: 42,
      by_type: { semantic: 20, episodic: 15, procedural: 7 },
    };
    render(<MemoryStats stats={stats} />);

    expect(screen.getByTestId("memory-stats")).toBeInTheDocument();
    expect(screen.getByTestId("total-memories")).toHaveTextContent("42");
    expect(screen.getByText(/semantic: 20/)).toBeInTheDocument();
    expect(screen.getByText(/episodic: 15/)).toBeInTheDocument();
    expect(screen.getByText(/procedural: 7/)).toBeInTheDocument();
  });

  it("MemoryCard shows delete button when onDelete is provided", () => {
    const onDelete = vi.fn();
    render(<MemoryCard memory={sampleMemory} onDelete={onDelete} />);

    expect(screen.getByTestId("delete-memory-btn")).toBeInTheDocument();
  });

  it("MemoryCard does not show delete button when onDelete is omitted", () => {
    render(<MemoryCard memory={sampleMemory} />);

    expect(screen.queryByTestId("delete-memory-btn")).not.toBeInTheDocument();
  });
});
