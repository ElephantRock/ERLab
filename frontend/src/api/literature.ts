import { apiFetchUnchecked } from "./client";
import { callContract, decodeObject, decodeString, decodeArray, type JsonContract } from "./contracts/common";

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

/** Response shape of GET /literature/ingested. */
export interface IngestedPapersResponse {
  ids: string[];
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

// F1.5c: contract-validated ingested-papers read — authoritative source of
// persisted ingestion state. The literature UI derives its "Ingested" badge
// from this response rather than from ephemeral client state, so the badge
// survives reload/remount and always reflects backend truth.
const ingestedPapersContract: JsonContract<IngestedPapersResponse> = {
  id: "literature.listIngested",
  method: "GET",
  pathPattern: "/literature/ingested",
  responseKind: "json",
  decoder: decodeObject<IngestedPapersResponse>({
    required: { ids: decodeArray(decodeString) },
  }),
};

/** Fetch the authoritative set of ingested paper IDs from the backend. */
export function listIngestedPapers(): Promise<IngestedPapersResponse> {
  return callContract(ingestedPapersContract);
}
