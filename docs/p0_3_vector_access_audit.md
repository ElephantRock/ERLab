# P0.3 Vector Access Audit

> **Status:** Complete inventory of every vector-store (ChromaDB) read and write
> in the production codebase, conducted before P0.3 scoping migration.

## Architecture

Four independent ChromaDB collections share one persistent directory (`./data/chroma`):

| Collection | Owner | Purpose | Scope key |
|---|---|---|---|
| `research_papers` | `VectorStore` | Paper chunk corpus | `paper_id` (per-doc, **NO run_id**) |
| `kg_entity_embeddings` | `GraphEmbeddingIndex` | KG entity vectors | `entity_type` |
| `tool_embeddings` | `ToolEmbeddingIndex` | Tool capability vectors | `trust_level` |
| `llm_cache` | `SemanticCache` | LLM response cache | none (global dedup) |

**P0.3 scope:** Only `research_papers` — the paper corpus — is in scope for run
scoping. The other three collections are infrastructure-level (KG, tools, cache)
and do not carry run ownership.

## Critical findings

1. **Single global corpus.** `research_papers` holds every ingested paper from
   every run plus every manual upload. Cross-run leakage is inherent.

2. **No run_id in vector metadata.** `VectorStore.add_papers` writes
   `paper_id, paper_title, source, section, year, keywords` — never `run_id`.
   Run scoping is impossible at query time even if filters were passed.

3. **Scope plumbing exists but is unused.** `TwoStageRetriever.retrieve(filter_metadata=)`
   and `VectorStore.query(filter_metadata=)` accept filters, but no production
   caller passes them. All queries are global.

4. **Two direct collection-access sites** bypass the wrapper:
   - `backend/api/routes/knowledge.py:91` — `store._collection.get(include=["metadatas"])`
   - `backend/api/routes/knowledge.py:246` — same pattern

5. **`delete_paper`** is paper-scoped but has zero production callers — stale
   data across runs is never pruned.

6. **GapAnalysisStage and IdeaGenerationStage do NOT touch ChromaDB.** They
   operate on in-memory `ctx.all_papers` and KG entities.

## Call-site classification

### Production vector reads (research_papers)

| Call site | Operation | Scope-aware? | Required P0.3 policy |
|---|---|---|---|
| `stages.py:135` LiteratureSearchStage | `store.query(domain, n_results=20)` for local_upload docs | NO (in-memory post-filter) | `selected_papers` or `current_run_only` |
| `novelty_checker.py:104` | `retriever.retrieve(query, top_k)` | NO | `current_run_only` |
| `novelty_checker.py:110` | `store.query(query, top_k)` fallback | NO | `current_run_only` |
| `builtin.py:56` vector_search tool | `store.query(query, n_results)` | NO | Caller must provide explicit scope |
| `knowledge.py:129` API /search | `store.query(query, top_k)` | NO | Caller must provide explicit scope |
| `knowledge.py:91` API /stats | `store._collection.get()` **direct** | NO | Maintenance only (not governed retrieval) |
| `knowledge.py:246` API /documents | `store._collection.get()` **direct** | NO | Maintenance only |
| `cli/main.py:694` CLI knowledge | `store.query(query, n_results)` | NO | Explicit legacy or caller scope |
| `retriever.py:117` TwoStageRetriever | `vector_store.query(q, fetch_count, filter_metadata)` | OPTIONAL (never passed) | Must receive resolved scope |
| `vector_store.py:198` query_by_embedding | `query(emb, n_results)` **no where** | NO | Must be replaced by scoped engine |

### Production vector writes (research_papers)

| Call site | Operation | run_id written? | Required P0.3 policy |
|---|---|---|---|
| `stages.py:523` IngestionStage | `store.add_papers(all_papers, chunks)` | NO | Must register via vector_index_records |
| `knowledge.py:211` API /ingest | `store.add_papers([paper], [chunks])` | NO | Explicit legacy or selected_papers |
| `cli/main.py:166` CLI ingest | `store.add_papers([paper], [chunks])` | NO | Explicit legacy |

### Stages that do NOT access ChromaDB

| Stage | Data source |
|---|---|
| GapAnalysisStage | In-memory `ctx.all_papers` + KG |
| IdeaGenerationStage | LLM provider + in-memory |
| FeasibilityScoringStage | LLM provider |
| ProposalSynthesisStage | LLM provider |
| MechanicalMetricsStage | In-memory computation |
| AdversarialReviewStage | LLM provider |
| CitationAuditStage | LLM provider + in-memory |
| ExportStage | SQLite KnowledgeLibrary (not ChromaDB) |

## Migration plan per call site

| Call site | Target mode | Migration wave |
|---|---|---|
| LiteratureSearchStage local_upload query | `selected_papers` | P0.3.4 |
| NoveltyChecker | `current_run_only` | P0.3.4 |
| vector_search tool | Caller-provided scope | P0.3.4 |
| API /search | Caller-provided scope | P0.3.4 |
| API /stats, /documents | Maintenance (allowlisted) | P0.3.4 |
| CLI knowledge | `query_vectors_legacy_unscoped` | P0.3.4 |
| IngestionStage write | `vector_indexer` + registry | P0.3.2 |
| API /ingest write | Legacy path | P0.3.4 |
| CLI ingest write | Legacy path | P0.3.4 |

## Default scope policies

| Stage / Service | Default mode |
|---|---|
| LiteratureSearch prior-paper prefetch | Disabled; explicit `same_domain_prior_runs` |
| GapAnalysis | `current_run_only` (operates on ctx, no ChromaDB) |
| NoveltyChecking | `current_run_only` |
| Synthesis/RAG | `current_run_only` |
| Citation/reference retrieval | `current_run_only` or explicit `selected_papers` |
| Knowledge-search API | Caller must provide explicit scope |
| User seed-paper workflow | `selected_papers` |
| Global knowledge exploration | Explicit `global_library` |
| Index verification | Direct registry/backend (not semantic retrieval) |
