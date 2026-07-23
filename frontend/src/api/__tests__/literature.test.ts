import { describe, it, expect, beforeEach, vi } from "vitest";
import { searchLiterature, ingestPaper, listIngestedPapers } from "@/api/literature";
import type { Paper, SearchResponse, LiteratureIngestResponse } from "@/api/literature";
import { apiFetchJson } from "@/api/client";

vi.mock("@/api/client", () => ({
  apiFetchUnchecked: vi.fn(),
  apiFetchJson: vi.fn(),
}));

const mockApiFetchJson = vi.mocked(apiFetchJson);

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
    // F1.7a: searchLiterature now uses callContract → apiFetchJson. Query
    // params are encoded by URLSearchParams inside withQuery, which emits
    // spaces as '+' (application/x-www-form-urlencoded) rather than '%20'.
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await searchLiterature("transformer attention");

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/literature/search?q=transformer+attention&max_results=10",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual(expected);
    expect(result.papers).toHaveLength(1);
    expect(result.papers[0].title).toBe("Attention Is All You Need");
  });

  it("TEST-23-02-07: searchLiterature() passes custom maxResults", async () => {
    const expected: SearchResponse = { papers: [] };
    mockApiFetchJson.mockResolvedValueOnce(expected);

    await searchLiterature("test", 25);

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/literature/search?q=test&max_results=25",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("TEST-23-02-07: ingestPaper() calls POST /literature/ingest with paper body", async () => {
    const expected: LiteratureIngestResponse = { status: "ingested", id: "ss-abc123" };
    // F1.4.1: ingestPaper now uses callContract → apiFetchJson
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await ingestPaper(samplePaper);

    expect(mockApiFetchJson).toHaveBeenCalled();
    expect(result).toEqual(expected);
    expect(result.status).toBe("ingested");
    expect(result.id).toBe("ss-abc123");
  });

  // ── F1.5c: listIngestedPapers uses callContract → apiFetchJson ──
  it("F1.5c: listIngestedPapers() returns authoritative persisted paper IDs", async () => {
    mockApiFetchJson.mockResolvedValueOnce({ ids: ["ss-1", "arxiv-2"] });

    const result = await listIngestedPapers();

    expect(mockApiFetchJson).toHaveBeenCalled();
    expect(result.ids).toEqual(["ss-1", "arxiv-2"]);
  });

  it("F1.5c: listIngestedPapers() rejects malformed responses (missing ids)", async () => {
    mockApiFetchJson.mockResolvedValueOnce({ wrong: "shape" });

    await expect(listIngestedPapers()).rejects.toThrow();
  });
});
