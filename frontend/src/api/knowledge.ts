import { apiFetch } from "./client";
import { API_PREFIX } from "@/lib/constants";
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

export async function ingestPdf(file: File): Promise<IngestResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const baseUrl = localStorage.getItem("erock_api_url") || "";
  const apiKey = localStorage.getItem("erock_api_key") || "";
  const headers: Record<string, string> = {};
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  const res = await fetch(`${baseUrl}${API_PREFIX}/knowledge/ingest`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const { ApiError } = await import("./client");
    throw new ApiError(res.status, body.detail || body.error?.message || res.statusText);
  }

  return res.json();
}
