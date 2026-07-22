import { apiFetchUnchecked } from "./client";
import { callContract, decodeObject, decodeString, type JsonContract } from "./contracts/common";

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
  return apiFetchUnchecked<SearchResponse>(
    `/literature/search?q=${encodeURIComponent(query)}&max_results=${maxResults}`,
  );
}

// F1.4.1: contract-validated ingest — no longer uses apiFetchUnchecked
const ingestPaperContract: JsonContract<LiteratureIngestResponse> = {
  id: "literature.ingestPaper",
  method: "POST",
  pathPattern: "/literature/ingest",
  responseKind: "json",
  decoder: decodeObject<LiteratureIngestResponse>({
    required: { status: decodeString, id: decodeString },
  }),
};

/** Ingest a paper into the knowledge base. */
export function ingestPaper(paper: Paper): Promise<LiteratureIngestResponse> {
  return callContract(ingestPaperContract, { body: paper });
}
