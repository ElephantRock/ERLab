/**
 * F1.7a — Group 3 endpoint contracts (knowledge, search, sessions).
 *
 * Migrates the remaining apiFetchUnchecked callers in:
 *   src/api/knowledge.ts   — searchKnowledge (POST), getKnowledgeStats (GET)
 *   src/api/search.ts      — globalSearch (GET)
 *   src/api/sessions.ts    — getSessionList (GET)
 *
 * Each decoder validates the material fields that consumers actually read
 * (see the page/component field-usage survey in the F1.7a migration notes).
 * Nested optional shapes are preserved via decodeObject's forward-compat
 * spread so unknown backend fields pass through as `unknown`.
 *
 * Literature (searchLiterature), memory (stats/recall/delete), and
 * notifications (markRead/markAllRead) contracts are co-located in their
 * respective api files because their domain types are declared locally
 * there (avoiding a circular import through this module).
 */

import {
  decodeArray,
  decodeNumber,
  decodeObject,
  decodeString,
  type JsonContract,
  type ResponseDecoder,
} from "./common";
import type {
  GlobalSearchResponse,
  KnowledgeSearchResponse,
  KnowledgeStats,
  SessionListResponse,
} from "@/api/types";

// ── Knowledge: semantic search ────────────────────────────────────────
// POST /knowledge/search → { query, results: [{ id, text, distance, metadata }] }
// The page (knowledge-search.tsx) reads result.id (key), result.text (display),
// result.distance (relevance coloring + label), and result.metadata.source /
// .year / .authors (badges). distance arrives as a number or null from the
// vector store; the type declares number, so we validate as number when present
// — a null distance is preserved via the optional path so the page's null-safe
// formatting still works. metadata values are heterogeneous (string | number);
// the type declares Record<string,string>, but the backend returns mixed
// primitives (e.g. year as number), so metadata is left as a passthrough
// object rather than validated as a string record.

export const searchKnowledgeContract: JsonContract<KnowledgeSearchResponse> = {
  id: "knowledge.search",
  method: "POST",
  pathPattern: "/knowledge/search",
  responseKind: "json",
  decoder: decodeObject<KnowledgeSearchResponse>({
    required: {
      query: decodeString,
      results: decodeArray(
        decodeObject<KnowledgeSearchResponse["results"][number]>({
          required: {
            id: decodeString,
            text: decodeString,
            metadata: decodeObject({ required: {} }),
          },
          optional: {
            distance: decodeNumber,
          },
        }),
      ),
    },
  }),
};

// ── Knowledge: stats ──────────────────────────────────────────────────
// GET /knowledge/stats → KnowledgeStats. The page reads total_documents and
// total_chunks (count displays); the provider/dir/model strings are surfaced
// in other surfaces and are material for diagnostics, so all five declared
// fields are required.

export const getKnowledgeStatsContract: JsonContract<KnowledgeStats> = {
  id: "knowledge.getKnowledgeStats",
  method: "GET",
  pathPattern: "/knowledge/stats",
  responseKind: "json",
  decoder: decodeObject<KnowledgeStats>({
    required: {
      chroma_persist_dir: decodeString,
      embedding_provider: decodeString,
      embedding_model: decodeString,
      total_documents: decodeNumber,
      total_chunks: decodeNumber,
    },
  }),
};

// ── Global search ─────────────────────────────────────────────────────
// GET /search/?q=...&types=... → GlobalSearchResponse. The dialog reads
// results.total and results.results.{ideas,gaps,papers,runs}[].items (each
// item has a typed shape). The four result buckets are all optional (the
// backend omits empty buckets), so they're validated only when present.

const ideaSearchItemDecoder = decodeObject<{
  id: number;
  title: string;
  domain: string;
  overall_score: number;
}>({
  required: {
    id: decodeNumber,
    title: decodeString,
    domain: decodeString,
    overall_score: decodeNumber,
  },
});

const gapSearchItemDecoder = decodeObject<{
  id: number;
  title: string;
  gap_type: string;
  confidence: number;
}>({
  required: {
    id: decodeNumber,
    title: decodeString,
    gap_type: decodeString,
    confidence: decodeNumber,
  },
});

const paperSearchItemDecoder = decodeObject<{
  id: number;
  title: string;
  year: number;
  venue: string;
}>({
  required: {
    id: decodeNumber,
    title: decodeString,
    year: decodeNumber,
    venue: decodeString,
  },
});

const runSearchItemDecoder = decodeObject<{
  id: number;
  status: string;
  domain: string;
  created_at: string;
}>({
  required: {
    id: decodeNumber,
    status: decodeString,
    domain: decodeString,
    created_at: decodeString,
  },
});

const searchBucketDecoder = <T>(itemDecoder: ResponseDecoder<T>) =>
  decodeObject<{ total: number; items: T[] }>({
    required: {
      total: decodeNumber,
      items: decodeArray(itemDecoder),
    },
  });

export const globalSearchContract: JsonContract<GlobalSearchResponse> = {
  id: "search.globalSearch",
  method: "GET",
  pathPattern: "/search/",
  responseKind: "json",
  decoder: decodeObject<GlobalSearchResponse>({
    required: {
      query: decodeString,
      total: decodeNumber,
      results: decodeObject<GlobalSearchResponse["results"]>({
        optional: {
          ideas: searchBucketDecoder(ideaSearchItemDecoder),
          gaps: searchBucketDecoder(gapSearchItemDecoder),
          papers: searchBucketDecoder(paperSearchItemDecoder),
          runs: searchBucketDecoder(runSearchItemDecoder),
        },
      }),
    },
  }),
};

// ── Sessions: list ────────────────────────────────────────────────────
// GET /pipeline/runs/sessions → { sessions: [{ session_id, run_count, latest_run_at }] }
// The page reads all three fields per session (id = key + name, run_count =
// badge, latest_run_at = formatted date).

export const getSessionListContract: JsonContract<SessionListResponse> = {
  id: "pipeline.getSessions",
  method: "GET",
  pathPattern: "/pipeline/runs/sessions",
  responseKind: "json",
  decoder: decodeObject<SessionListResponse>({
    required: {
      sessions: decodeArray(
        decodeObject<SessionListResponse["sessions"][number]>({
          required: {
            session_id: decodeString,
            run_count: decodeNumber,
            latest_run_at: decodeString,
          },
        }),
      ),
    },
  }),
};
