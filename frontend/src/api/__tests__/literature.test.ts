import { describe, it, expect, beforeEach, vi } from "vitest";
import { searchLiterature, ingestPaper } from "@/api/literature";
import type { Paper, SearchResponse, IngestResponse } from "@/api/literature";
import { apiFetch } from "@/api/client";

vi.mock("@/api/client", () => ({
  apiFetch: vi.fn(),
}));

const mockApiFetch = vi.mocked(apiFetch);

const samplePaper: Paper = {
  id: "ss-abc123",
  source: "semantic_scholar",
  title: "Attention Is All You Need",
  abstract: "We propose the Transformer architecture.",
  authors: [{ name: "Ashish Vaswani" }, { name: "Noam Shazeer" }],
  year: 2017,
  venue: "NeurIPS",
  citation_count: 50000,
  url: "https://arxiv.org/abs/1706.03762",
  doi: "10.5555/3295222.3295349",
  arxiv_id: null,
  keywords: [],
};

describe("BATCH-23/TASK-02: Literature API Client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── TEST-23-02-07: API client calls correct endpoints ──
  it("TEST-23-02-07: searchLiterature() calls correct endpoint with query params", async () => {
    const expected: SearchResponse = { papers: [samplePaper] };
    mockApiFetch.mockResolvedValueOnce(expected);

    const result = await searchLiterature("transformer attention");

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/literature/search?q=transformer%20attention&max_results=10",
    );
    expect(result).toEqual(expected);
    expect(result.papers).toHaveLength(1);
    expect(result.papers[0].title).toBe("Attention Is All You Need");
  });

  it("TEST-23-02-07: searchLiterature() passes custom maxResults", async () => {
    const expected: SearchResponse = { papers: [] };
    mockApiFetch.mockResolvedValueOnce(expected);

    await searchLiterature("test", 25);

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/literature/search?q=test&max_results=25",
    );
  });

  it("TEST-23-02-07: ingestPaper() calls POST /literature/ingest with paper body", async () => {
    const expected: IngestResponse = { status: "ingested", id: "ss-abc123" };
    mockApiFetch.mockResolvedValueOnce(expected);

    const result = await ingestPaper(samplePaper);

    expect(mockApiFetch).toHaveBeenCalledWith("/literature/ingest", {
      method: "POST",
      body: JSON.stringify(samplePaper),
    });
    expect(result).toEqual(expected);
    expect(result.status).toBe("ingested");
    expect(result.id).toBe("ss-abc123");
  });
});
