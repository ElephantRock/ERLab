# P0.3.4 Production Vector Migration Closeout

> **Status:** Production vector operations migrated to governed boundaries.
> P0.3.5 (legacy reindexing) and P0.3.6 (isolation closeout) remain open.

## Commits included in P0.3.4

| Commit | Wave | Description |
|---|---|---|
| `efef290` | P0.3.4A | Policy registry + architectural enforcement |
| `210dc2f` | P0.3.4B-C | Governed indexing + retrieval migration |
| `ed62cbf` | P0.3.4C-fix | Governed failures propagate, never fall through |
| `78f849e` | P0.3.4D | Governed knowledge-search API |
| *(this commit)* | P0.3.4E-I | Audit finalization, retrieval linkage, legacy module, closeout |

## Final access-audit table

| Module / Symbol | Operation | Run-aware | Classification | Governed policy | Implementation boundary | Provenance guard | Retrieval evidence | Architectural status |
|---|---|---|---|---|---|---|---|---|
| `stages.py` IngestionStage `_index_governed` | index | Yes (ctx.db_run_id) | `migrated_governed` | ingestion:index | VectorIndexer | load_run_provenance_contract | vector_index_records | Allowed (delegates to backend) |
| `stages.py` IngestionStage `store.add_papers` | index | No | `explicit_legacy_only` | None | Legacy VectorStore | Non-governed callers only | None | Legacy compat |
| `novelty_checker.py` `_retrieve_governed` | retrieve | Yes (run_id) | `migrated_governed` | novelty_check:retrieve, current_run_only | ScopedVectorService | load_run_provenance_contract | vector_retrieval_events | Allowed (delegates to backend) |
| `novelty_checker.py` `_retrieve_legacy` | retrieve | No | `explicit_legacy_only` | None | Legacy retriever/store | Non-governed callers only | None | Legacy compat |
| `knowledge.py` `/search/governed` | retrieve | Yes (run_id param) | `migrated_governed` | knowledge_search:retrieve | ScopedVectorService | load_run_provenance_contract | vector_retrieval_events | Allowed (delegates to backend) |
| `knowledge.py` `/search` | retrieve | No | `explicit_legacy_only` | None | Legacy VectorStore | Non-governed callers only | None | Legacy compat |
| `knowledge.py` `/stats`, `/documents` | verification | No | `maintenance_allowlisted` | None | Direct collection | Maintenance only | None | Allowlisted |
| `cli/main.py` ingest, knowledge, novelty | mixed | No | `explicit_legacy_only` | None | Legacy VectorStore | Non-governed callers only | None | Legacy compat |
| `builtin.py` vector_search tool | retrieve | No | `explicit_legacy_only` | None | Legacy VectorStore | Non-governed callers only | None | Legacy compat |
| GapAnalysisStage | — | — | `confirmed_non_vector` | — | — | — | — | N/A |
| IdeaGenerationStage | — | — | `confirmed_non_vector` | — | — | — | — | N/A |
| FeasibilityScoringStage | — | — | `confirmed_non_vector` | — | — | — | — | N/A |
| ProposalSynthesisStage | — | — | `confirmed_non_vector` | — | — | — | — | N/A |
| ExportStage | — | — | `confirmed_non_vector` | SQLite, not Chroma | — | — | — | N/A |

## Governed indexing path

```text
provenance_v1 run
→ IngestionStage._index_governed
→ load_run_provenance_contract → mode = governed
→ resolve embedding profile from settings
→ for each paper:
    → build_title_abstract_document (deterministic canonical text)
    → resolve canonical DB paper_id from source_id
    → VectorIndexer.index_document (atomic claim → embed → write → verify → indexed)
→ governed vector_index_records created
```

Legacy `store.add_papers` continues to run alongside for backward compatibility
during the P0.3.5 transition period. P0.3.5 will reindex legacy vectors and
quarantine the `research_papers` collection.

## Governed retrieval path

```text
provenance_v1 run
→ NoveltyChecker._retrieve_governed (or /search/governed API)
→ load_run_provenance_contract → mode = governed
→ resolve embedding profile
→ generate explicit query vector (no implicit backend embedding)
→ build VectorRetrievalScope (current_run_only default)
→ ScopedVectorService.query_vectors
  → resolve scope + freeze eligible records
  → coverage gate (empty/strict/partial)
  → candidate-constrained backend query
  → validate results against frozen snapshot
  → persist retrieval_event + results
→ return GovernedRetrievedContext with retrieval_event_id
```

For governed runs, ALL failures propagate. No legacy fallback.

## Retrieval artifact linkage

NoveltyChecker returns `similar` papers derived from `ScopedVectorRetrievalOutcome`.
The retrieval event identity (`retrieval_event_id`) is available to the calling
stage. The novelty profile artifact carries `retrieval_mode` to distinguish
governed vs legacy provenance.

## Knowledge-search API contract

### Governed endpoint: `POST /search/governed`

Required parameters:
- `run_id` (int) — must reference a provenance_v1 run
- `query` (str) — search text
- `scope_mode` — one of: current_run_only, same_domain_prior_runs, global_library, selected_papers
- `top_k` (int) — result limit
- `selected_paper_ids` (optional) — required for selected_papers scope

Response:
- `retrieval_event_id`, `scope_mode`, `coverage_status`, paper results with rank

### Legacy endpoint: `POST /search`

Retains existing behavior for non-governed callers. No governed run should
use this endpoint.

## Legacy compatibility boundary

Legacy vector access is isolated to:
- `pipeline/knowledge/vector_store.py` — the VectorStore class
- `novelty_checker.py._retrieve_legacy` — the legacy retrieval helper
- CLI commands, API `/search` endpoint, agent tools — all `explicit_legacy_only`

These paths are structurally separated from governed paths. The governed
path never calls them.

## Final architectural allowlist

Production modules allowed direct ChromaDB client construction:
- `vector_backend.py` — the governed backend adapter
- `vector_indexer.py` — the indexing lifecycle (uses GovernedVectorBackend)
- `scoped_vector_service.py` — the scoped query service
- `knowledge/vector_store.py` — legacy compat layer
- `knowledge/graph_embeddings.py` — KG entity embeddings (separate collection)
- `tools/tool_index.py` — tool capability index (separate collection)
- `providers/cache/semantic_cache.py` — LLM response cache (separate collection)

Temporary allowlist entries (construct GovernedVectorBackend inline, to be
refactored to service-registry injection in a future hardening pass):
- `novelty/novelty_checker.py`
- `pipeline/stages.py`
- `api/routes/knowledge.py`

## Zero-result and partial-coverage semantics

| Scenario | Behavior |
|---|---|
| Empty current-run scope | Success, zero results, zero backend calls |
| Strict incomplete coverage | Failure before backend query, no fallback |
| Explicit partial coverage | Query only indexed subset, audit records partial |
| No indexed records | Success with zero results (if partial allowed) |

## Resume and replay behavior

| Operation | Replay behavior |
|---|---|
| Indexed vector | `already_indexed` — no embedding call, no backend write |
| Successful retrieval | `replayed` — no backend query, same retrieval_event_id |
| Failed retrieval | Retryable with same input fingerprint |
| Running retrieval | Already-claimed error |

## Deferred work

- **P0.3.5:** Legacy vector inventory and deterministic reindexing of the
  `research_papers` collection into governed profile-specific collections.
- **P0.3.6:** Full isolation closeout — delete or quarantine legacy collection
  after verified reindexing.
- **P0.4:** Embedding capability handshake — verify the configured model is
  actually loaded and producing healthy embeddings.
- **Service-registry injection:** Refactor inline `GovernedVectorBackend`
  construction to use a central service bundle.
