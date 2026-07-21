import { apiFetch } from "./client";

// ── Types ──

export interface Author {
  name: string;
  id?: string | null;
  affiliations?: string[];
}

export interface Paper {
  id: string;
  source: string;
  title: string;
  abstract: string | null;
  authors: Author[];
  year: number | null;
  venue: string | null;
  citation_count: number | null;
  url: string | null;
  doi: string | null;
  arxiv_id: string | null;
  keywords: string[];
}

export interface SearchResponse {
  papers: Paper[];
}

// F1.1 M4: renamed from IngestResponse to LiteratureIngestResponse to
// disambiguate from the knowledge-ingest IngestResponse in api/types.ts
// (which has a different shape: {status, filename, chunks}). The two
// endpoints (/literature/ingest vs /knowledge/ingest) genuinely return
// different fields — the name collision was a maintenance trap.
export interface LiteratureIngestResponse {
  status: string;
  id: string;
}

// ── API Calls ──

/** Search academic literature across multiple sources. */
export function searchLiterature(
  query: string,
  maxResults: number = 10,
): Promise<SearchResponse> {
  return apiFetch<SearchResponse>(
    `/literature/search?q=${encodeURIComponent(query)}&max_results=${maxResults}`,
  );
}

/** Ingest a paper into the knowledge base. */
export function ingestPaper(paper: Paper): Promise<LiteratureIngestResponse> {
  return apiFetch<LiteratureIngestResponse>("/literature/ingest", {
    method: "POST",
    body: JSON.stringify(paper),
  });
}
