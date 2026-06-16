import { apiFetch, apiFetchFormData } from "./client";
import type { KnowledgeSearchResponse, KnowledgeStats, IngestResponse } from "./types";

export function searchKnowledge(query: string, topK = 20): Promise<KnowledgeSearchResponse> {
  return apiFetch("/knowledge/search", {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK }),
  });
}

export function getKnowledgeStats(): Promise<KnowledgeStats> {
  return apiFetch<KnowledgeStats>("/knowledge/stats");
}

/** Upload a PDF for knowledge base ingestion via shared FormData client. */
export function ingestPdf(file: File): Promise<IngestResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetchFormData<IngestResponse>("/knowledge/ingest", formData);
}
