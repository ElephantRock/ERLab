import { apiFetch } from "./client";
import type { KnowledgeSearchResponse } from "./types";

export function searchKnowledge(query: string, topK = 20): Promise<KnowledgeSearchResponse> {
  return apiFetch("/knowledge/search", {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK }),
  });
}
