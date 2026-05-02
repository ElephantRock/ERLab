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

export interface IngestResponse {
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
export function ingestPaper(paper: Paper): Promise<IngestResponse> {
  return apiFetch<IngestResponse>("/literature/ingest", {
    method: "POST",
    body: JSON.stringify(paper),
  });
}
