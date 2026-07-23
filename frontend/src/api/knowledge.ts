import {
  callContract,
  callFormDataContract,
  decodeNumber,
  decodeObject,
  decodeString,
  type FormDataContract,
} from "./contracts/common";
import {
  getKnowledgeStatsContract,
  searchKnowledgeContract,
} from "./contracts/group3";
import type { IngestResponse, KnowledgeSearchResponse, KnowledgeStats } from "./types";

// Re-export so existing `import { ... } from "@/api/knowledge"` still works
// for any consumer that referenced the type via this module.
export type { IngestResponse, KnowledgeSearchResponse, KnowledgeStats };

export function searchKnowledge(query: string, topK = 20): Promise<KnowledgeSearchResponse> {
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder.
  return callContract(searchKnowledgeContract, { body: { query, top_k: topK } });
}

export function getKnowledgeStats(): Promise<KnowledgeStats> {
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder.
  return callContract(getKnowledgeStatsContract);
}

// ── Knowledge: PDF ingest (FormData) ───────────────────────────────────
// F1.7a: migrated from a bare apiFetchFormData<T> cast to a contract-backed
// FormData transport with a runtime decoder. The upload endpoint returns
// { status, filename, chunks } per backend/api/routes/knowledge.py.

const ingestPdfContract: FormDataContract<IngestResponse> = {
  id: "knowledge.ingestPdf",
  method: "POST",
  pathPattern: "/knowledge/ingest",
  responseKind: "formdata",
  decoder: decodeObject<IngestResponse>({
    required: {
      status: decodeString,
      filename: decodeString,
      chunks: decodeNumber,
    },
  }),
};

/** Upload a PDF for knowledge base ingestion via a contract-backed FormData transport. */
export function ingestPdf(file: File): Promise<IngestResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return callFormDataContract(ingestPdfContract, formData);
}
