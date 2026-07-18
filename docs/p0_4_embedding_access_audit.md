# P0.4A0 — Embedding Access Audit

> **Status:** AUDIT-ONLY wave. No production code, no tests, no schema changed.
> Frozen taxonomy (§1.2 of `docs/p0_4_entry_contract.md`) applied to every
> executable surface. Frozen dispositions (§16 of same) verified against the
> actual repository at HEAD `35bf4c2`.

This document answers:

> What must P0.4B0 remove, consolidate, or instrument before a real
> capability handshake can govern every relevant embedding surface?

It does not propose B0 implementation; it produces the verified inventory
from which the B0 plan can be written.

## Audit method

Five parallel audit agents ran against `backend/` production code (tests,
`__pycache__`, `.venv`, migrations excluded unless noted). All file:line
references are absolute under `C:\Next-Era\Elephant-Rock-Research-Lab`.
Every executable call site received exactly one taxonomy class. Where
reachability could not be established, an explicit UNRESOLVED BLOCKER was
filed rather than a silent terminal class.

---

## 3.1 Executive inventory

| Metric                                                    | Count |
| --------------------------------------------------------- | ----: |
| Production embedding adapter classes (incl. wrappers)     |     7 |
| Production provider-construction factories                |     1 |
| Production document-embedding call sites                  |    11 |
| Production query-embedding call sites                     |    10 |
| Persistent side-channel vector writers                    |     5 |
| Persistent side-channel vector readers                    |     4 |
| Rebuildable cache embedding sites (writer + reader)       |     2 |
| `LLMProvider.embed()` base declarations                   |     1 |
| `LLMProvider.embed()` concrete implementations            |     5 |
| `LLMProvider.embed()` forwarder/proxy implementations    |     5 |
| `LLMProvider.embed()` direct non-wrapper production calls |     0 |
| `LLMProvider.embed()` transitive callers via EmbeddingService | 11 |
| Private inline `_EmbeddingAdapter` implementations        |     3 |
| Normalization implementations                             |     1 |
| Validation implementations (governed + side-channel)      |    17 |
| Version-literal sites (production)                        |    47 |
| Reranker / scoring-model classes                          |     6 |
| Confirmed scoring-only rerankers                          |     6 |
| Underlying reranker model-construction sites (handshake)  |     2 |
| **Unresolved call sites**                                 | **1** |

The single unresolved call site is **BLOCKER #1** in §3.3 (row 22) —
`NoveltyChecker._retrieve_governed` references `self._embedding` which is
never assigned in `__init__`. This is surfaced per directive §6 rather
than silently classified. It does not contradict any frozen disposition;
it is a pre-existing defect in governed novelty retrieval that P0.4B0/C
will need to address.

---

## 3.2 Provider adapter matrix

All adapters live in `backend/pipeline/knowledge/embedding_providers.py`
(total 412 lines). Base ABC `EmbeddingProvider` at `embedding_providers.py:28-46`
(exposes `embed(texts) -> list[list[float]]`, `dimension`, `provider_name`).

### OpenAIEmbeddingProvider — `embedding_providers.py:49-83`

| Field | Evidence |
|---|---|
| construction site | `embedding_providers.py:52` (`__init__`) |
| requested model source | constructor `model` arg, default `text-embedding-3-small`; factory wires `settings.embedding_model` |
| response model identity available? | **Yes** — OpenAI `/v1/embeddings` returns `response.model`; adapter discards it at `:75` |
| identity currently retained? | **No** — only `self._model` stored |
| possible resolution posture | **alias_only** — API is capable of `stable_deployment`, but current code is alias_only because it drops the served-model field |
| stable deployment input | would come from `response.model` (currently dropped) |
| document method | `embed(texts)` (`:73`) — no doc/query split |
| query method | `embed(texts)` (`:73`) — same |
| retry owner | adapter (no retry) |
| normalization owner | ERLab (`vector_runtime.py:44` declarative; ChromaDB `hnsw:space:cosine`) |
| dimension source | configuration — `_default_dimension` static dict (`:64-71`) |
| secret-bearing inputs | `api_key` (`:55`) → `openai.AsyncOpenAI(api_key=...)`; ambient `OPENAI_API_KEY` env |
| B0 changes required | (1) capture `response.model`; (2) store as `provider_revision`; (3) add `resolve_capability()`; (4) sanitize `api_key` in fingerprint; (5) optional `embed_documents`/`embed_query` split |
| adapter contract version | absent |

### GeminiEmbeddingProvider — `embedding_providers.py:86-120`

| Field | Evidence |
|---|---|
| construction site | `embedding_providers.py:89` |
| requested model source | constructor `model` arg, default `models/embedding-001` |
| response model identity available? | **No** — `genai.embed_content()` returns `{"embedding": [...]}` only |
| identity currently retained? | **No** — `self._model` only |
| possible resolution posture | **alias_only** — response carries no model identity; cannot reach `stable_deployment` without a separate API call |
| stable deployment input | would require external pinning + separate capability query |
| document method | `embed(texts)` (`:101`) — hardcoded `task_type="retrieval_document"` |
| query method | `embed(texts)` (`:101`) — **NO `retrieval_query` task_type variation** (same code path) |
| retry owner | adapter (none) |
| normalization owner | ERLab |
| dimension source | configuration — static dict (`:110-116`) |
| secret-bearing inputs | `api_key` (`:92`) → `genai.configure(api_key=...)` — **process-global state mutation**; hazard for coexistence with GeminiProvider (LLM) |
| B0 changes required | (1) add query/doc task_type split; (2) record requested model as only identity; (3) `resolve_capability` stub; (4) sanitize `api_key`; (5) document global-configure side effect for fingerprint stability |
| adapter contract version | absent |

### OllamaEmbeddingProvider — `embedding_providers.py:123-164`

| Field | Evidence |
|---|---|
| construction site | `embedding_providers.py:126` |
| requested model source | constructor `model` arg, default `nomic-embed-text`; `base_url` from `settings.ollama_base_url` (`:134-138`) |
| response model identity available? | **No** — `/api/embeddings` returns `{"embedding": [...]}` only |
| identity currently retained? | **No** — `self._model`, `self._base_url` |
| possible resolution posture | **alias_only** — Ollama resolves model tags to manifest+digest at request time; adapter never queries the digest; cannot be `stable_deployment` without a `/api/show` call |
| stable deployment input | would require `GET /api/show?name=<model>` to capture `digest` |
| document method | `embed(texts)` (`:144`) — one POST per text, no batch |
| query method | `embed(texts)` (`:144`) — same |
| retry owner | adapter (none) |
| normalization owner | ERLab |
| dimension source | **inferred** at runtime (`:154-155` — `self._dim = len(emb)` after first response) |
| secret-bearing inputs | `base_url` (`:129`); no API key |
| B0 changes required | (1) capture model digest via `/api/show`; (2) batch API (currently N HTTP calls for N texts); (3) `resolve_capability`; (4) sanitize `base_url`; (5) note inference-time dimension as fingerprint hazard |
| adapter contract version | absent |

### LMStudioEmbeddingProvider — `embedding_providers.py:167-251`

| Field | Evidence |
|---|---|
| construction site | `embedding_providers.py:192` |
| requested model source | constructor `model` arg, default `text-embedding-bge-m3-embeddings`; aliasing at `:203-204`; factory wires `settings.embedding_model`; `service_registry.py:63-77` actively queries LM Studio `/v1/models` to rename at runtime |
| response model identity available? | **Yes** — OpenAI-compatible `/v1/embeddings` returns `data.model`; adapter discards it at `:226-230` |
| identity currently retained? | **No** — only `self._model` (the requested/corrected name) |
| possible resolution posture | **alias_only** — adapter drops the echoed `model`. API is capable of `stable_deployment` because LM Studio reports loaded model `id` via `/v1/models` |
| stable deployment input | `service_registry.py:63-77` already resolves the loaded model id — natural source, currently logged then discarded |
| document method | `embed(texts)` (`:211`) — batches by `self._batch_size` (default 32) |
| query method | `embed(texts)` (`:211`) — same |
| retry owner | adapter — `try/except` at `:217/232` returns zero vectors on failure (`:239-241`). **Silently degrades rather than retrying or raising.** This is the only adapter with internal failure handling, and it is incorrect: the returned zeros collide with `EmbeddingService`'s zero-vector guard |
| normalization owner | ERLab |
| dimension source | configuration — `MODEL_DIMENSIONS` static dict (`:183-190`) |
| secret-bearing inputs | `base_url` (`:195`); no API key |
| B0 changes required | (1) capture `data.model` from response; (2) **stop returning zero vectors on failure** (let it raise); (3) thread `/v1/models` resolution from `service_registry.py:63-77` into instance as `provider_revision`; (4) `resolve_capability`; (5) sanitize `base_url` |
| adapter contract version | absent |

### Additional configured adapter classes

| Class | Location | Notes |
|---|---|---|
| `FallbackEmbeddingProvider` | `embedding_providers.py:254-278` | Wraps primary+fallback; one-shot primary→fallback on exception. Built at `service_registry.py:94` only when `settings.embedding_fallback_enabled`. No capability aggregation, no identity propagation |
| `DummyEmbeddingProvider` | `embedding_providers.py:281-300` | Zero-vector provider for offline/test; selected by factory when name ∈ {dummy, noop, test}. Production paths: `test_batch76_orchestrator.py`, `integration/test_pipeline_smoke.py` |
| `CachedEmbeddingProvider` | `embedding_providers.py:303-354` | In-memory SHA-256→vector cache. Auto-applied by factory for openai/gemini/lmstudio (`:399,412`); NOT for ollama (`:388-392`). Cache key is `hashlib.sha256(text_bytes)` (`:322`) — **text-content-derived, not model-derived; cache silently survives model revisions** |

### `create_embedding_provider` factory — `embedding_providers.py:357-412`

Dispatch: dummy/noop/test → Dummy (`:375`); openai → OpenAI (`:377`); gemini/google → Gemini (`:383`); ollama → Ollama (`:388`, NO cache wrap); lmstudio → LMStudio (`:393`, cache wrapped); openai-compatible/lm-studio → recursive call (`:400-407`). Unconditionally wraps cloud/LMStudio providers in `CachedEmbeddingProvider` (`:399, 412`). No retry wiring, no fallback wiring (fallback wired separately in `service_registry.py:88-94`). Receives `api_key` (`:360`) raw — no redaction layer.

### Critical cross-cutting findings

1. **Zero of four providers capture served-model identity today.** All four are functionally `alias_only`. The handshake cannot certify any binding as `stable_deployment` without B0 adapter surgery.
2. **`LMStudioEmbeddingProvider.embed` returns zero vectors on failure** (`embedding_providers.py:239-241`), contradicting `EmbeddingService`'s fail-closed contract at `embedding_service.py:80-84`.
3. **`CachedEmbeddingProvider` keys on text content only** (`:322`) — changing the underlying model does NOT invalidate the cache. Silent correctness bug for B0 model-revision tracking.
4. **`GeminiEmbeddingProvider` mutates process-global SDK state** via `genai.configure(api_key=...)` (`:97`) — unsafe coexistence with GeminiProvider (LLM).
5. **`AnthropicProvider.embed`** (in the LLMProvider surface, §3.4) secretly re-instantiates `openai.AsyncOpenAI()` at `anthropic_provider.py:209` — hidden cross-provider dependency on ambient `OPENAI_API_KEY`.

---

## 3.3 Embedding call-site ledger

Every executable production call site. Taxonomy class is one of:
`handshake_boundary` · `governed_paper_embedding` · `governed_query_embedding`
· `side_channel_persistent_embedding` · `ephemeral_or_rebuildable_cache_embedding`
· `explicit_test_provider` · `explicit_legacy_only` · `maintenance_only`
· `removed_dead_code` · `confirmed_non_embedding_model`.

### Production write/read of governed embeddings

| # | module:symbol (file:line) | taxonomy | role | provider surface | profile? | binding today | B0 action | C/D action | risk |
|---|---|---|---|---|---|---|---|---|---|
| 18 | `index_document` embed_single — `vector_indexer.py:344` | governed_paper_embedding | document | private adapter | yes | strict via `validate_embedding` + read-back | preserve | verified-runtime target | low |
| 19 | `IngestionStage._index_governed` + inline `_EmbeddingAdapter` — `stages.py:676-690` | governed_paper_embedding | document | private adapter | yes (runtime.profile_dict) | inherited from `index_document` | preserve | verified-runtime integration | medium |
| 20 | `build_governed_vector_runtime_from_settings` + inline `_EmbeddingAdapter` — `vector_runtime.py:88-116` | governed_paper_embedding | document+query | private adapter | yes | inherited | preserve | verified-runtime integration | medium |
| 21 | `ScopedVectorRetrievalRequest.query_vector` consumer — `scoped_vector_service.py:161` | governed_query_embedding | query | n/a (consumer) | yes | strict via `validate_query_vector` | preserve | verified-runtime compatible | low |
| **22** | **`NoveltyChecker._retrieve_governed` — `novelty_checker.py:160`** ⚠️ | governed_query_embedding *(intent)* | query | `self._embedding.embed_texts` | yes (runtime.profile_id) | **UNRESOLVED BLOCKER #1** — `self._embedding` is never assigned in `__init__` (lines 77-91); governed novelty retrieval raises `AttributeError` on every call | **fix in B0** — inject `EmbeddingService` into `NoveltyChecker.__init__` or use `runtime.embedding_provider.embed_single` | verified-runtime integration | **critical** |
| 23 | `search_knowledge_governed` embed_texts — `knowledge.py:230` | governed_query_embedding | query | `EmbeddingService.embed_texts` constructed at request time | yes (runtime.profile_id) | downstream via scoped service | preserve | verified-runtime integration | medium |

### Side-channel persistent embeddings

| # | module:symbol (file:line) | taxonomy | role | provider surface | profile? | binding today | B0 action | C/D action | risk |
|---|---|---|---|---|---|---|---|---|---|
| 39 | `GraphEmbeddingIndex.index_entity` — `graph_embeddings.py:45` | side_channel_persistent_embedding | entity | `EmbeddingService.embed_single` | **no** | none | **instrument** | bind to verified runtime | high |
| 40 | `GraphEmbeddingIndex.index_graph` — `graph_embeddings.py:62` | side_channel_persistent_embedding | entity | `EmbeddingService.embed_texts` | **no** | none | **instrument** | bind to verified runtime | high |
| 41 | `GraphEmbeddingIndex.query_similar` — `graph_embeddings.py:80` | side_channel_persistent_embedding | query | `EmbeddingService.embed_single` | **no** | none | **instrument** | bind to verified runtime | high |
| 42 | `ToolEmbeddingIndex.index_tool` — `tool_index.py:55` | side_channel_persistent_embedding | tool | `EmbeddingService.embed_single` | **no** | none | **instrument** | bind to verified runtime | high |
| 43 | `ToolEmbeddingIndex.index_registry` — `tool_index.py:73` | side_channel_persistent_embedding | tool | `EmbeddingService.embed_texts` | **no** | none | **instrument** | bind to verified runtime | high |
| 44 | `ToolEmbeddingIndex.query` — `tool_index.py:98` | side_channel_persistent_embedding | query | `EmbeddingService.embed_single` | **no** | none | **instrument** | bind to verified runtime | high |

### Rebuildable cache embedding

| # | module:symbol (file:line) | taxonomy | role | provider surface | profile? | binding today | B0 action | C/D action | risk |
|---|---|---|---|---|---|---|---|---|---|
| 45 | `SemanticCache.lookup_similar` — `semantic_cache.py:53` | ephemeral_or_rebuildable_cache_embedding | cache key | `EmbeddingService.embed_single` | **no** | none | instrument | optional | medium |
| 46 | `SemanticCache.update_similar` — `semantic_cache.py:98` | ephemeral_or_rebuildable_cache_embedding | cache key | `EmbeddingService.embed_single` | **no** | none | instrument | optional | medium |
| 47 | `provider_factory._wrap_cached` constructs separate EmbeddingService — `provider_factory.py:303-324` | ephemeral_or_rebuildable_cache_embedding | cache key | second independent `EmbeddingService` | **no** | none | consolidate | optional | medium |

### Legacy Chroma paths (`research_papers` collection, frozen but present)

| # | module:symbol (file:line) | taxonomy | role | provider surface | B0 action | risk |
|---|---|---|---|---|---|---|
| 24 | `VectorStore.__init__` dim check + collection recreate — `vector_store.py:46-70` | explicit_legacy_only | (store) | EmbeddingService | preserve (frozen) | medium |
| 25 | `VectorStore.add_papers` embed_texts — `vector_store.py:95` | explicit_legacy_only | document | `EmbeddingService.embed_texts` | preserve (frozen) | high |
| 26 | `VectorStore.query` embed_single — `vector_store.py:164` | explicit_legacy_only | query | `EmbeddingService.embed_single` | preserve (frozen) | high |
| 27 | `LiteratureSearchStage.execute` constructs EmbeddingService + VectorStore + `store.query(ctx.domain)` — `stages.py:131-135` | explicit_legacy_only | query | EmbeddingService.embed_single | preserve (frozen) | high |
| 28 | `knowledge.py:knowledge_stats` — `knowledge.py:84` | explicit_legacy_only | n/a | n/a (stats only) | preserve | low |
| 29 | `knowledge.py:search_knowledge` — `knowledge.py:133-136` | explicit_legacy_only | query | EmbeddingService.embed_single | preserve (frozen) | high |
| 30 | `knowledge.py:ingest_document` — `knowledge.py:351-360` | explicit_legacy_only | document | EmbeddingService.embed_texts | preserve (frozen) | high |
| 31 | `knowledge.py:list_documents` — `knowledge.py:392` | explicit_legacy_only | n/a | n/a | preserve | low |
| 32 | `pipeline.py` stats construction — `pipeline.py:1486-1492` | explicit_legacy_only | n/a | n/a | preserve | low |
| 33 | `ideas.py` constructs EmbeddingService+VectorStore+NoveltyChecker — `ideas.py:497-507` | explicit_legacy_only | query | EmbeddingService.embed_single | preserve (frozen) | high |

### CLI / maintenance

| # | module:symbol (file:line) | taxonomy | role | provider surface | B0 action | risk |
|---|---|---|---|---|---|---|
| 34 | `cli/main.py:154` `_ingest` → `store.add_papers` | maintenance_only | document | EmbeddingService.embed_texts | mark maintenance | medium |
| 35 | `cli/main.py:400` `_check` constructs EmbeddingService+VectorStore+NoveltyChecker | maintenance_only | query | EmbeddingService.embed_single | mark maintenance | medium |
| 36 | `cli/main.py:484` `_stats` constructs VectorStore | maintenance_only | n/a | n/a | preserve | low |
| 37 | `cli/main.py:692` `_search` → `store.query` | maintenance_only | query | EmbeddingService.embed_single | mark maintenance | medium |
| 38 | `legacy_vector_cli._execute_reindex` + inline `_EmbeddingAdapter` — `legacy_vector_cli.py:282-310` | maintenance_only | document | private adapter | preserve | medium |

### Dead code (verified)

| # | module:symbol (file:line) | taxonomy | notes | B0 action |
|---|---|---|---|---|
| 49 | `EmbeddingSimilarity._batch_embed` — `memory/embedding_dedup.py:63` | removed_dead_code | `EmbeddingSimilarity` is never instantiated in production | remove |
| 50 | `EmbeddingSimilarity._get_embedding` — `embedding_dedup.py:70` | removed_dead_code | same | remove |
| 51 | `ClaimStore._find_via_embedding` — `claims/store.py:114` | removed_dead_code | `embedding_service` is always None in production; comment at `:121-123` confirms full embedding search is a stub | remove embed branch |
| 52 | `RelevanceFilter.filter` — `literature/relevance_filter.py:66,73` | removed_dead_code | production `SearchService` always constructed with `embedding_provider=None`; `SearchIntegrationService` has zero production callers | remove or wire |

### Provider ABCs, factories, and service-layer wrappers (handshake boundary)

Rows #1–#17 in the underlying agent ledger cover the ABC definition, four
provider classes, factory, `EmbeddingService` constructor/methods,
`validate_embedding`, `_verify_readback`, `validate_query_vector`, and the
profile-id computation. All classify as `handshake_boundary`. They are
omitted from the tables above for brevity but counted in the executive
inventory. Key coordinates:

- `EmbeddingProvider` ABC — `embedding_providers.py:28`
- `EmbeddingService.__init__` (with warn-only `validate_dimension`) — `embedding_service.py:43,136-146`
- `EmbeddingService.embed_texts` (zero-vector rejection + exception wrap) — `embedding_service.py:57`
- `EmbeddingService.embed_single` — `embedding_service.py:89`
- `EmbeddingService.validate_startup` — `embedding_service.py:104`
- `validate_embedding` (strict, fail-closed) — `vector_indexer.py:124-154`
- `_verify_readback` (strict) — `vector_indexer.py:175-202`
- `validate_query_vector` (strict, fail-closed) — `scoped_vector_service.py:79-102`
- `compute_profile_id` — `vector_contracts.py:260`

### Count per taxonomy class (executable rows)

| taxonomy class | count |
|---|---:|
| handshake_boundary | 17 |
| governed_paper_embedding | 3 |
| governed_query_embedding | 3 |
| side_channel_persistent_embedding | 6 |
| ephemeral_or_rebuildable_cache_embedding | 3 |
| explicit_test_provider | 1 |
| explicit_legacy_only | 10 |
| maintenance_only | 5 |
| removed_dead_code | 4 |
| confirmed_non_embedding_model (executable call sites) | 0 |

(7 additional interface-conformance rows for `LLMProvider.embed` and its
forwarders are not call sites — see §3.4.)

---

## 3.4 `LLMProvider.embed()` removal graph

Per frozen disposition §16.4, this surface is to be **removed** from
production in P0.4B0.

| Layer | Location |
|---|---|
| protocol/base declaration | `backend/providers/base.py:181` — `async def embed(self, texts: list[str]) -> list[list[float]]` (abstract) |
| OpenAI implementation | `backend/providers/openai_provider.py:294` |
| Ollama implementation | `backend/providers/ollama_provider.py:182` |
| Anthropic implementation | `backend/providers/anthropic_provider.py:205` — **hidden cross-provider dependency**: re-instantiates `openai.AsyncOpenAI()` at `:209`, depends on ambient `OPENAI_API_KEY` |
| LiteLLM implementation | `backend/providers/litellm_provider.py:220` |
| Gemini implementation | `backend/providers/gemini_provider.py:166` |
| CachedProvider forwarding | `backend/providers/cache/cached_provider.py:169` |
| GatewayProvider forwarding | `backend/pipeline/gateway/gateway_provider.py:265` — comment: "Embeddings bypass the gateway" |
| ResilientProvider forwarding | `backend/providers/resilience/resilient_provider.py:137` — only retry path for embeddings anywhere |
| StageContext forwarding | `backend/providers/stage_context.py:158` |
| StageWrapper forwarding | `backend/providers/stage_wrapper.py:86` |
| test doubles and fixtures | 24 test `embed` definitions across 26 test files |

### Direct production callers (non-wrapper, non-forwarder, non-dead)

**0.** Confirmed by two independent audit agents. The canonical call site
is `EmbeddingService.embed_texts()` at `embedding_service.py:72` — itself a
wrapper, and only invokes `LLMProvider.embed()` when constructed with an
`LLMProvider` rather than a dedicated `EmbeddingProvider`.

### Transitive callers via EmbeddingService (these must migrate before removal)

| Site | file:line | Status |
|---|---|---|
| Vector runtime builder | `backend/pipeline/vector_runtime.py:96-97` | **required-live** — feeds `_EmbeddingAdapter` into GovernedVectorRuntime |
| CLI legacy vector reindex | `backend/cli/legacy_vector_cli.py:300-302` | **required-live** — `embed_single` invoked by `execute_reindex_targets` |
| CLI ingest | `backend/cli/main.py:154` | **required-live** — `VectorStore.add_papers` |
| CLI query | `backend/cli/main.py:400` | **required-live** — `VectorStore.query` |
| CLI stats | `backend/cli/main.py:484` | **required-live** (may trigger embed) |
| CLI doctor | `backend/cli/main.py:692` | **required-live** |
| Knowledge route (stats) | `backend/api/routes/knowledge.py:84` | wrapper-only — `get_stats()` does not embed |
| Knowledge route (query) | `backend/api/routes/knowledge.py:133` | **required-live** — `store.query()` calls `embed_single` |
| Knowledge route (add) | `backend/api/routes/knowledge.py:227` | **required-live** — add path embeds |
| Knowledge route (update) | `backend/api/routes/knowledge.py:351` | **required-live** |
| Knowledge route (delete) | `backend/api/routes/knowledge.py:392` | wrapper-only — delete typically does not embed |

### Required migrations before removal

To remove `LLMProvider.embed()` and its 5 concrete implementations, the 8
**required-live** transitive callers must migrate from `create_provider()`
(LLMProvider) to `create_embedding_provider()` (EmbeddingProvider). After
migration, the `EmbeddingService` type annotation (`embedding_service.py:48`)
can drop the `LLMProvider` union member and the abstract `embed()` plus
its 5 concrete impls can be deleted. The 5 forwarders (CachedProvider,
GatewayProvider, ResilientProvider, StageContext, StageWrapper) lose their
`embed` methods in the same wave.

---

## 3.5 Private adapter consolidation

Three byte-identical `_EmbeddingAdapter` classes, none exposing
`dimension` / `provider_name` / normalization. No additional inline
adapter classes found in production (other `*Adapter` classes are not
embedding-related: `StrategyAdapter`, `MCPToolAdapter`, `ToTAdapter`,
scoring normalizers).

| # | location | inputs | methods | identity? | dimension? | normalization | callers |
|---|---|---|---|---|---|---|---|
| 1 | `backend/pipeline/stages.py:676-682` | `embedding_service` | `embed_single(text)` | No | No | none | `IngestionStage._index_governed` → `index_document` |
| 2 | `backend/pipeline/vector_runtime.py:99-104` | `svc` | `embed_single(text)` | No | No | none | three GVR consumers (stages fallback, novelty fallback, governed API) |
| 3 | `backend/cli/legacy_vector_cli.py:289-294` | `svc` | `embed_single(text)` | No | No | none | `_execute_reindex` — constructs an additional EmbeddingService independent of the runtime's |

### Consolidation recommendation

All three should be replaced by a single canonical adapter class living
next to `EmbeddingService` (e.g. `embedding_service.py` or
`vector_runtime.py`) that also surfaces `dimension` and `provider_name`
so the governed profile handshake can resolve model identity from the
adapter instead of from settings. The recommendation does NOT pick one
existing private implementation arbitrarily — it establishes one governed
adapter contract.

---

## 3.6 `GovernedVectorRuntime` migration ledger

Current shape at `backend/pipeline/vector_runtime.py:18-32` — six fields.

### Construction sites

| # | site | symbol |
|---|---|---|
| C1 | `backend/pipeline/vector_runtime.py:35-85` | `build_governed_vector_runtime` |
| C2 | `backend/pipeline/vector_runtime.py:88-116` | `build_governed_vector_runtime_from_settings` (wraps C1 at `:106`) |
| C3 | `backend/pipeline/vector_runtime.py:99-104` | inline `_EmbeddingAdapter` (inside C2) |
| C4 | `backend/pipeline/stages.py:676-682` | inline `_EmbeddingAdapter` (DUPLICATE — second byte-identical copy) |

### Caller-by-caller field-read matrix

| # | caller (file:line) | constructs runtime? | reads `.embedding_provider`? | reads `.embedding_profile_id`? | reads `.profile_dict`? | reads `.session_factory`? | reads `.db_engine`? | reads `.backend`? | required post-B0 replacement |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|---|
| G1 | `stages.py:628` (import) + `:634` (call) — IngestionStage fallback | YES | no | yes (`:639`) | yes (`:640`) | yes (`:641`) | no | yes (`:642`) | `indexer` + `retrieval_service` + typed `profile_snapshot` |
| G2 | `stages.py:630-631` — IngestionStage injected branch | no | no | yes (`:639`) | yes (`:640`) | yes (`:641`) | no | yes (`:642`) | same as G1 |
| G3 | `novelty_checker.py:148-149` — `_retrieve_governed` fallback | YES | no | yes (`:155`) | no | yes (`:157`) | no | yes (`:156`) | `retrieval_service` only |
| G4 | `novelty_checker.py:142-143` — `_retrieve_governed` injected | no | no | yes (`:144`) | no | yes (`:146`) | no | yes (`:145`) | `retrieval_service` only |
| G5 | `knowledge.py:215,217` — `/search/governed` | YES | no | yes (`:224`) | no | yes (`:257`) | no | yes (`:258`) | `retrieval_service`; capability belongs on runtime as typed service |
| G6 | `legacy_vector_cli.py:39,284` — `_execute_reindex` | YES | no | no (uses caller-supplied `profile_id`) | yes (`:304`) | no | no | yes (`:298`) | `indexer` + typed `profile_snapshot` |

### Dead fields (zero production readers)

- `embedding_provider` — written at `vector_runtime.py:74`, **never read**
- `db_engine` — written at `vector_runtime.py:84`, **never read**

Both are pure dead weight on the dataclass. The embedding provider is
re-derived from settings at each caller site; `db_engine` is only used
inside `build_governed_vector_runtime_from_settings` to build the
session_factory, never after construction.

### `runtime.backend` field reads (all 5)

1. `backend/pipeline/stages.py:642`
2. `backend/pipeline/novelty/novelty_checker.py:145`
3. `backend/pipeline/novelty/novelty_checker.py:156`
4. `backend/api/routes/knowledge.py:258`
5. `backend/cli/legacy_vector_cli.py:298`

Every consumer hands raw `backend` straight into a lower-level service
(`index_document`, `query_vectors`, `execute_reindex_targets`). Post-B0
these become `indexer.index(...)` / `retrieval_service.query(...)` and
`backend` is no longer exposed.

---

## 3.7 Side-channel collections

### `kg_entity_embeddings` — INCLUDED per §16.1

| concern | evidence |
|---|---|
| collection construction | `graph_embeddings.py:33-36` — `get_or_create_collection(name=collection_name or "kg_entity_embeddings", metadata={"hnsw:space": "cosine"})` |
| production construction callers | 2 sites — `service_registry.py:282-285` (`init_cross_refs`, via `EmbeddingNoveltyScorer`) and `service_registry.py:712-715` (`init_graph_rag`, via `GraphRAGRetriever`). **Both use the same persist_dir and same embedding service** — two GraphEmbeddingIndex instances pointing at the same collection |
| writer symbols | `index_entity` (`:43-54`), `index_graph` (`:56-75`) |
| reader/query symbols | `query_similar` (`:77-101`, used by `embedding_scorer.py:54`), `query_by_embedding` (`:103-124`, GraphRAGRetriever internals) |
| metadata contract | per-record `{"entity_type", "name"}`. Collection-level: `{"hnsw:space": "cosine"}` only — **no provider/model/dimension recorded** |
| implicit embedding usage | `embed_single(text)` (`:45`), `embed_texts(texts)` (`:62`) |
| provider source | single shared `EmbeddingService` from `service_registry.py:79-99` |
| profile identity | **NO** — no `EmbeddingProfile` reference anywhere |
| dimension handling | implicit only; no validation, no expected-dim argument |
| normalization | none explicit; relies on `hnsw:space:cosine` |
| deletion/rebuild behavior | **NONE** — no clear/delete/reset/rebuild method; only manual ChromaDB directory wipe |
| allowlist status | CONFIRMED — `docs/p0_3_4_production_vector_migration_closeout.md:116` |
| existing tests | `test_graph_rag/test_graph_embeddings.py` — 12 sites |
| **mixed-model risk** | **HIGH** — collection has no provider/model metadata; constructor does not pin a model; queries do not filter by model. Operator changing `settings.embedding_model` produces mixed-model collection silently; cosine scores across models are meaningless |

### `tool_embeddings` — INCLUDED per §16.2

| concern | evidence |
|---|---|
| collection construction | `tool_index.py:40-43` |
| production construction callers | 1 site — `service_registry.py:747-750` (`init_tool_discovery`, via `ToolMatcher`) |
| writer symbols | `index_tool` (`:53-65`), `index_registry` (`:67-90`), `ToolMatcher.refresh_index` (`tool_matcher.py:64-67`) |
| reader symbols | `query` (`:92-119`, used by `ToolMatcher.find_tools`) |
| metadata contract | per-record `{"trust_level", "source", "description"}`. Collection-level: `{"hnsw:space": "cosine"}` only |
| implicit embedding usage | `embed_single` (`:55`), `embed_texts` (`:73`) |
| provider source | shared `EmbeddingService` |
| profile identity | **NO** |
| dimension handling | implicit only |
| normalization | none explicit |
| deletion/rebuild behavior | **NONE** on `ToolEmbeddingIndex`. `refresh_index` re-bulks-upserts but does NOT clear stale entries — removed tools persist forever |
| allowlist status | CONFIRMED — `docs/p0_3_4_production_vector_migration_closeout.md:117` |
| existing tests | `test_tool_discovery/test_tool_index.py` (10), `test_tool_matcher.py` (12), `test_tool_discovery_integration.py` (6) |
| **mixed-model risk** | **MEDIUM-HIGH** — same root cause as KG; only one production construction site lowers the risk slightly |

### `llm_cache` — capability-gated per §16.3, NO durable cutover

| concern | evidence |
|---|---|
| collection construction | `semantic_cache.py:43-46` |
| production construction caller | 1 site — `provider_factory.py:318-324` (`_wrap_cached`, only when `cache_type == "semantic"`) |
| writer symbols | `update_similar` (`:97-113`), `CachedProvider._store_semantic` (`cached_provider.py:55-59`) |
| reader symbols | `lookup_similar` (`:52-95`), `CachedProvider._check_semantic` (`cached_provider.py:43-50`) |
| metadata contract | **NONE** — upsert at `:105-109` passes only `ids`, `embeddings`, `documents`. Serialized LLM response stored as ChromaDB `document` |
| implicit embedding usage | `embed_single` (`:53`, `:98`) |
| provider source | **separate** `EmbeddingService` constructed at `provider_factory.py:307-317` — second EmbeddingService in the process, distinct from collections A/B |
| profile identity | **NO** |
| dimension handling | implicit only; `settings.embedding_dimension` is a hint only |
| normalization | none explicit |
| deletion/rebuild behavior | `clear` (`:128-139`) deletes entire collection; `_evict_oldest` (`:115-119`), `_invalidate` (`:121-126`) remove single entries. **CRITICAL: `_timestamps` is in-memory only (`:50`), not persisted** — on restart all TTL state is lost while ChromaDB persists. `clear()` is never invoked by any production caller |
| allowlist status | CONFIRMED — `docs/p0_3_4_production_vector_migration_closeout.md:118` |
| existing tests | `test_caching/test_semantic_cache.py` |
| **mixed-model risk** | **HIGH and uniquely dangerous** — collection has NO per-record metadata; queries use `n_results=1` with no model filter; returns LLM RESPONSE on similarity ≥ 0.95 (`:72`); a cross-model false-positive returns a verbatim stale answer to a different question; `clear()` exists but is never called so cache only grows |

### Cross-cutting finding

All three collections plus the GVR's own `_EmbeddingAdapter` rely on a
single process-wide configured `EmbeddingService` whose identity is never
recorded at write time. Any operator change to `settings.embedding_model`
or `settings.embedding_provider` silently produces a mixed-model
collection with no detection, no quarantine, and (for `llm_cache`)
actively incorrect HIT responses.

---

## 3.8 Configuration and profile reconciliation

### Runtime configuration (Settings) — `backend/config.py`

`class Settings(BaseSettings)` at `config.py:20`, env prefix `EROCK_` (`:24`).

| field | file:line | type | default |
|---|---|---|---|
| `embedding_provider` | `config.py:62` | str | `"openai"` |
| `embedding_model` | `config.py:63` | str | `"text-embedding-bge-m3-embeddings"` |
| `embedding_dimension` | `config.py:64` | int | `1536` |
| `embedding_batch_size` | `config.py:65` | int | `100` |
| `embedding_fallback_enabled` | `config.py:66` | bool | `False` |
| `embedding_base_url` | `config.py:67` | str | `""` (falls back to `lmstudio_base_url`) |

- **Endpoint / base URL**: `embedding_base_url` (`:67`), `lmstudio_base_url` (`:93`), `ollama_base_url` (`:42`), `vllm_base_url` (`:103`)
- **Provider credentials (names only)**: `openai_api_key` (`:37`), `anthropic_api_key` (`:39`), `gemini_api_key` (`:41`), `pubmed_api_key` (`:56`), `semantic_scholar_api_key` (`:51`), `api_key` (`:116`). **No `embedding_*_api_key` field exists** — embedding reuses `openai_api_key` (see `provider_factory.py:310`)
- **Document/query task parameters**: **ABSENT** in Settings. Only hardcoded literal at `embedding_providers.py:106` (`task_type="retrieval_document"` for Gemini)
- **Normalization / post-processing configuration**: **ABSENT** in Settings. The only source of `normalization_policy` is the default parameter at `vector_runtime.py:43` (`"l2"`)
- **Chunking schema configuration**: **ABSENT** in Settings. Hardcoded default at `vector_runtime.py:44` (`"title_abstract_v1"`)

### Registered profile (`EmbeddingProfile`) — `backend/db/models.py:1270-1296`

CHECK constraints (`models.py:1278-1283`):
- `ck_ep_schema_version` (`:1279`): `profile_schema_version = 'embedding_profile_v1'`
- `ck_ep_verification_status` (`:1280`): `verification_status = 'unverified'` — **single allowed value today**
- `ck_ep_dimension_positive` (`:1281`): `dimension > 0`
- `uq_ep_collection_name` (`:1282`): unique `collection_name`

Columns: `profile_id` (`:1285`), `profile_schema_version` (`:1286`), `provider` (`:1287`), `model_identifier` (`:1288`), `dimension` (`:1289`), `normalization_policy` (`:1290`), `chunking_schema_version` (`:1291`), `collection_name` (`:1292`), `verification_status` (`:1293`).

**Notable**: no CHECK on `provider` / `model_identifier` / `normalization_policy` values; `verification_status` is locked to `'unverified'` (P0.4 must alter this constraint).

### Profile registration / lookup sites

- Registration function: `vector_indexer.py:52` (`register_embedding_profile`)
- Row insert: `vector_indexer.py:105-117`
- Production caller: `vector_indexer.py:231` (inside `index_document`)
- Lookup by `profile_id` (replay check): `vector_indexer.py:76-78`
- Lookup by `collection_name` (collision check): `vector_indexer.py:93-98`
- Lookup by `profile_id` at query time: `scoped_vector_service.py:195-199`
- Lookup by `profile_id` at CLI: `legacy_vector_cli.py:103-105`

### Drift surfaces for P0.4A2 to reconcile

1. **`vector_indexer.py:82-89`** — single drift gate for provider/model/dimension/normalization/chunking (raises `EmbeddingProfileDriftError`)
2. **`vector_runtime.py:88-113`** — Settings→profile bridge with hardcoded `normalization_policy="l2"` and `chunking_schema_version="title_abstract_v1"` defaults
3. **`embedding_service.py:54-55,136-146`** — `expected_dimension` plumbing missing from runtime construction; `validate_dimension` only warns, never raises
4. **`embedding_providers.py:64-71,110-116,158-160,183-209`** — provider-reported `.dimension` **never compared** to `Settings.embedding_dimension` or `EmbeddingProfile.dimension`. Soft check exists at `EmbeddingService.validate_dimension` but is warn-only and not wired by `vector_runtime.py:97`
5. **`provider_factory.py:307-317`** — separate semantic-cache construction path with its own dimension default, not the runtime profile

---

## 3.9 Version-literal inventory

`capability_v1` and `pre_capability_v0`: **CONFIRMED ABSENT** (zero hits
anywhere in repo, including tests).

| literal | production sites | test sites |
|---|---|---|
| `vector_index_v1` | 9 — `db/models.py:{1316,1355}` (db_constraint), `vector_contracts.py:249` (identity_computation), `vector_backend.py:67` (backend_metadata), `vector_indexer.py:{171,197}` (indexer_write, retrieval_eligibility), `scoped_vector_service.py:139` (retrieval_eligibility), `alembic/versions/022_vector_index_registry.py:{74,97}` (db_constraint) | 7 |
| `embedding_profile_v1` | 4 — `db/models.py:1279` (db_constraint), `vector_contracts.py:269` (identity_computation), `vector_indexer.py:107` (indexer_write), `alembic/versions/022_vector_index_registry.py:44` (db_constraint) | 8 |
| `source_query_v1` | 7 — `literature/contracts.py:{83,97}`, `arxiv_source.py:58`, `crossref_source.py:78`, `openalex_source.py:58`, `pubmed_source.py:61`, `semantic_scholar.py:61` | 8 |
| `resolved_vector_scope_v1` | 2 — `vector_contracts.py:98`, `vector_scope.py:98` | 0 |
| `legacy_identity_v1` | 4 — `legacy_vector_inventory.py:{77,241,633,644}` | 5 |
| `vector_scope_v1` | 6 — `vector_contracts.py:77`, `vector_scope.py:{56,58}`, `vector_access_policy.py:67`, `knowledge.py:238`, `novelty_checker.py:168` | ~10 |
| `vector_retrieval_v1` | 5 — `vector_contracts.py:142`, `scoped_vector_service.py:{305,615}`, `knowledge.py:246`, `novelty_checker.py:176` | 0 |
| `vector_document_v1` | 2 — `vector_contracts.py:{182,214}` | 1 |
| `legacy_vector_inventory_v1` | 2 — `db/models.py:1510`, `legacy_vector_inventory.py:432` | 0 |
| `legacy_mapping_v1` | 1 — `legacy_vector_inventory.py:35` | 0 |
| `global_library_v1` | 2 — `db/models.py:1235`, `alembic/versions/021_vector_scope_foundation.py:65` | 1 |
| `vector_access_policy_v1` | 7 — `vector_access_policy.py:{18,85,95,105,115,125,135}` | 0 |
| `erlab_vectors_v1_` prefix | 1 — `vector_contracts.py:283` (collection-name derivation) | 0 |

**Total production sites: 47** across 12 distinct literals.

### B0 extraction scope (per §6 of contract — constants for v1 + v2)

The B0 extraction must at minimum cover:
- `VECTOR_INDEX_V1 = "vector_index_v1"` and `VECTOR_INDEX_V2 = "vector_index_v2"` — replaces 9 production literals
- `EMBEDDING_CONTRACT_PRE_CAPABILITY_V0 = "pre_capability_v0"` and `EMBEDDING_CONTRACT_CAPABILITY_V1 = "capability_v1"` — currently absent, introduced as constants
- `EMBEDDING_PROFILE_V1 = "embedding_profile_v1"` — replaces 4 production literals

Other literals (`source_query_v1`, `vector_scope_v1`, etc.) may be
extracted opportunistically but are not load-bearing for P0.4 v2 identity.

---

## 3.10 Normalization and validation inventory

### Provider raw output validation (inside `EmbeddingProvider` subclasses)

**NONE.** No subclass validates its own output — all return SDK output
verbatim, with the exception of `LMStudioEmbeddingProvider` which returns
zero vectors on failure (`embedding_providers.py:240`).

### Application post-processing — `EmbeddingService`

| file:line | function | validates |
|---|---|---|
| `embedding_service.py:36-40` | `_is_zero_vector` | zero-vector rejection (does NOT handle numpy explicitly, unlike `vector_store.py:22-33`) |
| `embedding_service.py:65-66` | `embed_texts` empty-input short-circuit | only legitimate zero-vector path |
| `embedding_service.py:73-76` | `embed_texts` batch loop | wraps provider exception in `EmbeddingProviderError` |
| `embedding_service.py:79-84` | `embed_texts` | zero-vector rejection per batch (raises) |
| `embedding_service.py:104-134` | `validate_startup` | probes single test embedding for non-empty/non-zero (line 124 duplicates zero-vector logic inline) |
| `embedding_service.py:136-146` | `validate_dimension` | dimension match — **warn-only**, never raises |

**Missing at this layer**: numeric isinstance, bool rejection, finite-value check, dimension-as-error, result-count check.

### `VectorIndexer` validation

| file:line | function | validates |
|---|---|---|
| `vector_indexer.py:124-154` | `validate_embedding` | None, list/tuple isinstance, empty, dimension match, bool rejection, numeric isinstance, **finite-value** (`math.isnan`/`math.isinf`), zero-vector rejection |
| `vector_indexer.py:175-202` | `_verify_readback` | paper_id/chunk_key/content_kind/content_hash/profile_id/schema_version metadata match + dimension |

### `ScopedVectorService` validation

| file:line | function | validates |
|---|---|---|
| `scoped_vector_service.py:79-102` | `validate_query_vector` | None, str/bytes rejection, list/tuple, empty, dimension, bool rejection, numeric isinstance, finite-value, zero-vector |
| `scoped_vector_service.py:105-110` | `validate_top_k` | int isinstance, bool rejection, positivity |
| `scoped_vector_service.py:426-431` | inline | result must be in eligible_set (scope violation) |
| `scoped_vector_service.py:433-438` | inline | `match.paper_id == snap.paper_id` (backend_metadata_mismatch) |
| `scoped_vector_service.py:440-444` | inline | **finite distance check** (`math.isnan`/`math.isinf`) |
| `scoped_vector_service.py:447-454` | inline | duplicate-vector-record rejection |
| `scoped_vector_service.py:457-463` | inline | trim to top_k with deterministic ordering |

### Side-channel validation

- `vector_store.py:22-33` `_is_zero_vector` — **different impl** from `embedding_service._is_zero_vector` (handles numpy.ndarray explicitly)
- `vector_store.py:54-70` `VectorStore.__init__` — **dimension drift detection**: compares stored dim vs `embedding_service.dimension`; **auto-recreates collection** on mismatch (side effect, not exception)
- `vector_store.py:105-111` `VectorStore.add_papers` — per-embedding zero-vector rejection at write (**warning + skip, not exception**)
- `graph_embeddings.py:64` — `if emb` truthy filter only (no zero/finite/dim check)
- `tool_index.py:75` — same `if emb` truthy filter
- `semantic_cache.py:54,99` — inline `if not query_embedding or all(v == 0.0 for v in query_embedding)` — **third independent zero-vector implementation**

### Cosine-similarity norm computations (assume but do not verify unit norm)

- `embedding_dedup.py:74-82` `_cosine_similarity` — own norms, zero-norm guard at `:80`
- `literature/relevance_filter.py:101-110` `_cosine_similarity` — separate impl, own norms, zero-norm guard at `:108`
- `compaction/paper_selector.py:130-140` `_cosine_similarity` — **third impl**, uses `min_len` slicing (allows different lengths), zero-norm guard at `:138`
- `compaction/paper_selector.py:107-127` `_simple_embedding` — **the only place in production code that actually L2-normalizes a vector**; bag-of-words proxy, not a real embedding

### Duplicated / inconsistent implementations

| concern | implementations | inconsistency |
|---|---|---|
| zero-vector check | 3 impls across 6 sites (`embedding_service:36-40`, `vector_store:22-33`, `semantic_cache:54,99` inline, `vector_indexer:151`, `scoped_vector_service:100`) | numpy handling differs; `semantic_cache` re-inlines |
| embedding-shape validation | `vector_indexer.validate_embedding` and `scoped_vector_service.validate_query_vector` | near-identical; query adds str/bytes rejection; failure-code prefixes differ |
| cosine similarity | `embedding_dedup`, `relevance_filter`, `paper_selector` | 3 impls; `paper_selector` accepts different lengths; none validates finite or unit-norm |
| dimension match | warn (`embedding_service:136`), silent-recreate (`vector_store:54-70`), hard-fail (`vector_indexer:140`, `scoped_vector_service:91`, `_verify_readback:199`) | **5 sites, 3 behaviors** — P0.4 must pick one canonical contract |
| finite-value check | only `vector_indexer:148`, `scoped_vector_service:{98,440}` | absent in providers, EmbeddingService, all side-channels — NaN/Inf can leak into Chroma |
| result-count check | **ABSENT** | no site verifies `len(embeddings) == len(input_texts)` |
| bool rejection | `vector_indexer:144-145`, `scoped_vector_service:94-95` | consistent in 2 governed sites, absent in 4 other layers |
| L2 normalization of embedding output | **NONE in production** | `normalization_policy="l2"` is declarative-only |

---

## 3.11 Rerankers and scoring models

All in `backend/pipeline/knowledge/reranker.py` plus thin orchestration.

| # | module & symbol (file:line) | model class | output | persistence | taxonomy | P0.4 action |
|---|---|---|---|---|---|---|
| 1 | `JinaCrossEncoderReranker` `reranker.py:47` | `transformers.AutoModel` (jinaai/jina-reranker-v3) via `model.rerank()` | scalar scores (`ScoredDocument.score`) | no — transient sort of `ctx.all_papers` | `confirmed_non_embedding_model` | excluded |
| 2 | `LMStudioReranker` `reranker.py:215` | LM Studio chat completions, prompt-based | scalar scores | no | `confirmed_non_embedding_model` | excluded |
| 3 | `LLMReranker` `reranker.py:317` | wraps `LLMProvider`; `provider.complete()` with scoring prompt | scalar scores | no | `confirmed_non_embedding_model` | excluded |
| 4 | `CrossEncoderReranker` `reranker.py:381` | `sentence_transformers.CrossEncoder` (`:393-395`); `_model.predict(pairs)` (`:410`) | scalar scores (`:416`) | no | `confirmed_non_embedding_model` | excluded |
| 5 | `RemoteReranker` `reranker.py:425` | HTTP to remote `/v1/rerank` | scalar scores | no | `confirmed_non_embedding_model` | excluded |
| 6 | `create_reranker` factory `reranker.py:511` | dispatches to #1–#5 | passthrough | no | `confirmed_non_embedding_model` | excluded |
| — | `_heuristic_rerank` `reranker.py:185` | no model | scalar scores | no | `confirmed_non_embedding_model` | excluded |

### Underlying model-construction sites (handshake_boundary, future work)

| site | model | action |
|---|---|---|
| `reranker.py:100-103` | `AutoModel.from_pretrained("jinaai/jina-reranker-v3", trust_remote_code=True)` | future model-handshake work — loads arbitrary code via `trust_remote_code=True` |
| `reranker.py:393-395` | `CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")` | future model-handshake work |

Neither emits reusable vectors nor writes to a vector store, so neither
is `side_channel_persistent_embedding`. Reranker production wiring:
`service_registry.py:113-127` (constructs), `stage_lifecycle.py:298-323`
(invokes), `retriever.py:213-233` (TwoStageRetriever calls).

### Other scoring-relevance sites

`compaction/paper_selector.py:107` `_simple_embedding` is a bag-of-words
hash pseudo-embedding (no model, transient, in-memory cosine ranking).
`relevance_score` references in `literature/*` and `evaluation/*` are
upstream API score fields or LLM-judge outputs, not local models.

**Confirmed scoring-only reranker count: 6 classes + 1 factory + 1
heuristic = 8 sites, all `confirmed_non_embedding_model`.**

---

## 4. Repository search contract — verified coverage

All required symbols searched via ripgrep in production code. Notable
results:

| symbol | production occurrences |
|---|---|
| `embed(` | 36 matches in 16 files |
| `embed_single` | 16 matches in 10 files |
| `embed_documents` / `embed_query` | **0** (langchain-style API not used) |
| `EmbeddingProvider` | 39 in 5 files |
| `EmbeddingService` | 47 in 17 files |
| `_EmbeddingAdapter` | 6 in 3 files |
| `embedding_dimension` | 23 in 12 files |
| `vector_index_v1` | 9 in 5 production files (+7 test) |
| `kg_entity_embeddings` / `tool_embeddings` / `llm_cache` | 1 each (ChromaDB collection constants) |
| `GovernedVectorRuntime` | 5 in 2 files |
| `build_governed_vector_runtime_from_settings` | 9 in 5 files |

### Newly-discovered sites flagged beyond the original anchor list

These were not in the original audit anchor list but were surfaced by the
residual sweep:

1. **`backend/api/routes/knowledge.py`** — 6 inline `EmbeddingService(create_provider())` constructions (lines 84, 133, 227, 351, 392) + `build_governed_vector_runtime_from_settings` (`:217`) + raw `query_embeddings` (`:230`)
2. **`backend/api/routes/ideas.py`** — mixed `create_provider()` + `create_embedding_provider()` wiring (`:473-505`)
3. **`backend/api/routes/pipeline.py:1483-1491`** — inline embedding provider construction
4. **`backend/cli/main.py`** — 4 inline `EmbeddingService(create_provider())` constructions (`:152-154,399-401,483-485,691-693`)
5. **`backend/pipeline/novelty/embedding_scorer.py`** (`EmbeddingNoveltyScorer`) — instantiated at `service_registry.py:286` (production)
6. **`backend/providers/provider_factory.py:294-334`** (`_wrap_cached`) — constructs `SemanticCache` inline

### Dynamic provider registries verified

- `backend/providers/provider_factory.py:20` `ProviderRegistry` — primary LLM factory, singleton via `_get_registry()` (`:213`)
- `backend/pipeline/knowledge/embedding_providers.py:357` `create_embedding_provider` — dict-dispatch factory
- `backend/plugins/registry.py:24` `PluginRegistry` — no embeddings (verified)
- `backend/pipeline/orchestrator/composition_root.py:56` — uses `get_registry()` for plugins, no embedding construction
- `backend/pipeline/strategies/registry.py:7` `StrategyRegistry` — prompt strategies, no embeddings

No embedding surfaces under `backend/pipeline/agents/` or
`backend/pipeline/autonomy/` (verified zero matches).

---

## 5. B0 work ledger

Actionable work items grouped per directive. Each item lists files,
symbols, callers, expected tests, breaking-change risk, and dependency
ordering. **This is the verified inventory — not the implementation
plan.**

### B0.1 — Provider response-identity capture

| field | value |
|---|---|
| files | `backend/pipeline/knowledge/embedding_providers.py` |
| symbols | `OpenAIEmbeddingProvider.embed`, `LMStudioEmbeddingProvider.embed`, `OllamaEmbeddingProvider.embed`, `GeminiEmbeddingProvider.embed` |
| current callers | `EmbeddingService.embed_texts` (`embedding_service.py:72`); `preflight._check_embedding_provider` (`preflight.py:190`) |
| expected tests | per-provider response capture (mock the SDK response, assert identity retained); round-trip through EmbeddingService |
| breaking-change risk | medium — adds fields to provider objects; CachedEmbeddingProvider cache key must be invalidated on identity change |
| dependency ordering | independent; can land first |

Concrete captures required:
- OpenAI: read `response.model` (`embedding_providers.py:75` — currently discarded)
- LMStudio: read `data["model"]` from response (`:226-230` — currently discarded); also thread `/v1/models` resolution from `service_registry.py:63-77`
- Ollama: add `GET /api/show?name=<model>` call to capture digest
- Gemini: external pinning only (API returns no model identity)

### B0.2 — Provider resolution-posture classification

| field | value |
|---|---|
| files | `backend/pipeline/knowledge/embedding_providers.py` |
| symbols | all four provider classes + `FallbackEmbeddingProvider` + `CachedEmbeddingProvider` |
| current callers | factory `create_embedding_provider`; service_registry wiring |
| expected tests | per-provider posture assertion (alias_only today; stable_deployment after B0.1); FallbackEmbeddingProvider must aggregate child postures honestly |
| breaking-change risk | low — adds a `resolve_capability()` method and `model_resolution_posture` field |
| dependency ordering | depends on B0.1 |

Critical rule (per §1.3 of contract): **no adapter may upgrade an alias
to a stable identity merely because the provider echoed the requested
model name.** Each adapter explicitly classifies the evidence as
`exact_revision`, `stable_deployment`, or `alias_only`.

### B0.3 — Private adapter consolidation

| field | value |
|---|---|
| files | `backend/pipeline/stages.py:676-682`, `backend/pipeline/vector_runtime.py:99-104`, `backend/cli/legacy_vector_cli.py:289-294` |
| symbols | three `_EmbeddingAdapter` classes (byte-identical) |
| current callers | `IngestionStage._index_governed`, three GVR consumers, `_execute_reindex` |
| expected tests | governed adapter exposes `dimension` + `provider_name`; all three call sites use the canonical adapter |
| breaking-change risk | low — pure consolidation, behavior preserved |
| dependency ordering | independent; should land before B0.6 (GVR migration) so the canonical adapter is in place |

The canonical adapter must surface `dimension` and `provider_name` so the
governed profile handshake can resolve model identity from the adapter
rather than from settings.

### B0.4 — `LLMProvider.embed()` removal

| field | value |
|---|---|
| files | `backend/providers/base.py:181`, `openai_provider.py:294`, `ollama_provider.py:182`, `anthropic_provider.py:205`, `litellm_provider.py:220`, `gemini_provider.py:166`, `cache/cached_provider.py:169`, `gateway/gateway_provider.py:265`, `resilience/resilient_provider.py:137`, `stage_context.py:158`, `stage_wrapper.py:86`; **migration sites** — `vector_runtime.py:96-97`, `legacy_vector_cli.py:300-302`, `cli/main.py:{154,400,484,692}`, `api/routes/knowledge.py:{84,133,227,351,392}`, `embedding_service.py:48` |
| symbols | `LLMProvider.embed` + 5 concrete impls + 5 forwarders |
| current callers (transitive) | 8 required-live + 3 wrapper-only = 11 sites |
| expected tests | every migrated site uses `create_embedding_provider`; architectural test for reintroduction of `.embed()` on LLMProvider |
| breaking-change risk | **high** — 11 call sites must migrate in the same wave or in dependency order; Anthropic implementation has hidden OpenAI SDK dependency (`anthropic_provider.py:209`) that must be resolved separately |
| dependency ordering | migration of the 11 sites can begin after B0.1 (so the dedicated `EmbeddingProvider` has identity capture); removal of the abstract + concrete impls must come after all migrations verified |

### B0.5 — Side-channel adapter preparation

| field | value |
|---|---|
| files | `backend/pipeline/knowledge/graph_embeddings.py`, `backend/pipeline/tools/tool_index.py`, `backend/providers/cache/semantic_cache.py` |
| symbols | `GraphEmbeddingIndex`, `ToolEmbeddingIndex`, `SemanticCache` |
| current callers | `service_registry.py:{282,712,747}` (KG/Tool), `provider_factory.py:318` (cache) |
| expected tests | each collection accepts (or requires) a profile_id; collection metadata records provider/model/dimension; mixed-model write is rejected |
| breaking-change risk | high for KG (two production construction sites share a collection), medium for Tool, low for cache (rebuilt on binding change per §16.3) |
| dependency ordering | depends on B0.1 and B0.2 (need identity capture before binding); must coordinate with B0.6 if collections receive the typed profile_snapshot |

Each collection gains a profile reference, a binding-aware namespace, and
provider/model/dimension in collection metadata. KG and Tool gain
rebuild methods (currently absent); cache gains binding-invalidation of
old entries (currently absent).

### B0.6 — `GovernedVectorRuntime` migration preparation

| field | value |
|---|---|
| files | `backend/pipeline/vector_runtime.py`, `backend/pipeline/stages.py`, `backend/pipeline/novelty/novelty_checker.py`, `backend/api/routes/knowledge.py`, `backend/cli/legacy_vector_cli.py` |
| symbols | `GovernedVectorRuntime` dataclass, both builders, 6 caller sites |
| current callers | G1–G6 (see §3.6) |
| expected tests | every migrated caller reads only the post-B0 fields (`capability_service`, `indexer`, `retrieval_service`, `profile_snapshot`); the two dead fields (`embedding_provider`, `db_engine`) are removed |
| breaking-change risk | **high** — breaking change to a heavily-used dataclass; all 6 callers must migrate in the same wave |
| dependency ordering | depends on B0.3 (canonical adapter); should land alongside B0.1/B0.2 so the new runtime can carry `capability_service` |

Dropped-field-read gate (per §13.1 of contract, invariant 3): **0
migrated callers reading removed `embedding_provider` or `profile_dict`
fields** at closeout. Today's field-read counts to eliminate:
`embedding_provider` 0 (already dead), `db_engine` 0 (already dead),
`profile_dict` 2 reads (`stages.py:640`, `legacy_vector_cli.py:304`),
`backend` 5 reads (become `indexer`/`retrieval_service` calls).

### B0.7 — Settings/profile reconciliation preparation

| field | value |
|---|---|
| files | `backend/config.py`, `backend/pipeline/vector_runtime.py`, `backend/pipeline/vector_indexer.py`, `backend/pipeline/knowledge/embedding_service.py`, `backend/pipeline/knowledge/embedding_providers.py`, `backend/providers/provider_factory.py` |
| symbols | `Settings.embedding_*`, `EmbeddingProfile.*`, `build_governed_vector_runtime_from_settings`, `register_embedding_profile`, `EmbeddingService.validate_dimension`, per-provider `.dimension` |
| current callers | all GVR construction sites; all profile registration sites |
| expected tests | settings/profile disagreement raises `configuration` failure; `validate_dimension` becomes fail-closed; provider `.dimension` cross-checked against Settings and Profile |
| breaking-change risk | medium — strict drift checks may surface previously-silent misconfigurations |
| dependency ordering | depends on B0.1 (need provider-reported dimension); can land in parallel with B0.6 |

Five drift surfaces to close (per §3.8):
1. `vector_indexer.py:82-89` drift gate
2. `vector_runtime.py:88-113` Settings bridge (hardcoded defaults)
3. `embedding_service.py:54-55,136-146` warn-only dimension (must fail-close)
4. `embedding_providers.py:64-71,110-116,158-160,183-209` provider dimension never compared
5. `provider_factory.py:307-317` separate cache construction path

### B0.8 — Vector/version constants extraction

| field | value |
|---|---|
| files | `backend/pipeline/vector_contracts.py` (constants defined here); 9 `vector_index_v1` sites + 4 `embedding_profile_v1` sites replaced |
| symbols | new `VECTOR_INDEX_V1`, `VECTOR_INDEX_V2`, `EMBEDDING_CONTRACT_PRE_CAPABILITY_V0`, `EMBEDDING_CONTRACT_CAPABILITY_V1`, `EMBEDDING_PROFILE_V1` |
| current callers | all 47 production version-literal sites (B0 focus on the 13 vector/contract/profile sites; other literals opportunistic) |
| expected tests | no behavior change; grep test confirms zero remaining `vector_index_v1` string literals in production |
| breaking-change risk | low — pure refactor |
| dependency ordering | independent; should land first to unblock B0.5 (collection metadata) and B0.6 (runtime contract version) |

### B0.9 — Architectural enforcement preparation

| field | value |
|---|---|
| files | new test module (e.g. `backend/tests/test_pipeline/test_p0_4_architectural_seal.py`); scan targets: `embedding_providers.py`, `vector_runtime.py`, all `_EmbeddingAdapter` sites, all `create_provider` → EmbeddingService sites |
| symbols | AST-based scan for raw-provider construction outside allowlist; reintroduction of `LLMProvider.embed()`; direct `.embed()` calls outside verified runtime |
| current callers | n/a — new enforcement |
| expected tests | the architectural test itself |
| breaking-change risk | low — additive test |
| dependency ordering | must land AFTER B0.4 (LLMProvider.embed removal) and B0.6 (GVR migration); otherwise it will fail |

### Suggested sequencing

```text
B0.8 (constants)              independent, unblocks B0.5/B0.6
B0.3 (adapter consolidation)  independent, unblocks B0.6
B0.1 (identity capture)       unblocks B0.2, B0.5, B0.7
B0.2 (posture classification) depends on B0.1; unblocks B0.5, B0.7
B0.7 (settings/profile)       depends on B0.1; parallel with B0.6
B0.6 (GVR migration)          depends on B0.1, B0.3; parallel with B0.7
B0.5 (side-channel prep)      depends on B0.1, B0.2, B0.6
B0.4 (LLMProvider.embed removal) depends on B0.1; high-risk, late in wave
B0.9 (architectural seal)     depends on B0.4, B0.6
```

The BLOCKER #1 fix (NoveltyChecker:160) can land anywhere in B0 but
should be early since it unblocks governed novelty testing.

---

## 6. Stop conditions — evaluation

Per directive §6, audit must stop and surface if repository evidence
shows any of:

| stop condition | evaluation |
|---|---|
| a frozen side-channel disposition is technically impossible | NOT TRIGGERED — all three collections can accept profile/binding metadata; mixed-model risk is high but fixable via B0.5 |
| `LLMProvider.embed` has a required production caller that cannot migrate | NOT TRIGGERED — all 8 required-live callers can migrate to `create_embedding_provider`; no caller requires the LLMProvider surface specifically |
| a provider cannot expose even an honest alias/deployment posture | NOT TRIGGERED — all 4 providers can at minimum honestly declare `alias_only`; OpenAI/LMStudio can reach `stable_deployment` after B0.1; Ollama can via `/api/show`; Gemini requires external pinning but can declare `alias_only` honestly |
| runtime profile identity cannot be linked to current settings | NOT TRIGGERED — 5 drift surfaces identified (§3.8) but all closeable in B0.7 |
| an embedding surface writes persistent vectors without a discoverable reader | NOT TRIGGERED — all three side-channel collections have discoverable readers (see §3.7) |
| an executable embedding path cannot be assigned one taxonomy class | NOT TRIGGERED — all executable paths assigned exactly one class. NoveltyChecker:160 (BLOCKER #1) is assigned `governed_query_embedding` by intent but flagged as a non-executable code defect |

**No stop conditions triggered.** The audit proceeds to closeout with
one surfaced blocker (BLOCKER #1) that does not contradict any frozen
disposition.

---

## 7. P0.4A0 completion gate

Per directive:

| criterion | status |
|---|---|
| production embedding call sites unclassified | **1 unresolved** (BLOCKER #1, surfaced explicitly per §6) |
| persistent vector collections unclassified | 0 |
| raw-provider construction sites unclassified | 0 |
| `LLMProvider.embed` symbols unaccounted | 0 (1 base + 5 concrete + 5 forwarders all listed in §3.4) |
| `GovernedVectorRuntime` callers unaccounted | 0 (6 callers + 4 constructions in §3.6) |
| private embedding adapters unaccounted | 0 (3 in §3.5) |
| rerankers without vector/scoring classification | 0 (8 sites in §3.11) |
| frozen dispositions silently contradicted | 0 |
| production code changes during A0 | 0 |

### Honest disclosure

The directive's completion gate requires "unresolved call sites = 0."
The audit surfaces **1 unresolved call site** rather than silently
classifying it. This is a deliberate choice per directive §6: "When
reachability cannot be established, classify the item as an explicit
unresolved blocker rather than silently assigning a terminal class."

The unresolved site (`NoveltyChecker._retrieve_governed` at
`novelty_checker.py:160`) is a pre-existing production defect (referenced
attribute never assigned in `__init__`). The intended taxonomy class
(`governed_query_embedding`) is unambiguous, but the code path is
non-executable as written. This blocker does not prevent B0 from
proceeding — it becomes an explicit B0 work item (fix in B0, before
governed novelty retrieval can be exercised end-to-end).

### Status

```text
P0.4-pre       CLOSED — 2273b37 / evidence 35bf4c2
P0.4A0         COMPLETE (this commit) — 1 blocker surfaced per §6
P0.4B0         READY (B0 work ledger above defines scope; blocker fix is in-scope)
P0.4A1+        BLOCKED pending B0
```

---

## Appendix — Audit method and agent coverage

Five parallel audit agents covered the 9 directive sub-areas:

1. Provider adapter matrix + LLMProvider.embed production-caller verification
2. Embedding call-site ledger + private adapter consolidation
3. GovernedVectorRuntime migration ledger + side-channel collections
4. Settings/profile reconciliation + version-literal inventory + normalization/validation inventory
5. Reranker classification + residual symbol sweep + independent re-verification of LLMProvider.embed production callers

The two independent verifications of `LLMProvider.embed()` production
caller count (agents 1 and 5) **agreed**: direct non-wrapper non-dead
callers = **0**. The 11 transitive callers via EmbeddingService are
listed in §3.4 with their migration status.

No file was modified during this audit. The working tree remains at
`35bf4c2`.
