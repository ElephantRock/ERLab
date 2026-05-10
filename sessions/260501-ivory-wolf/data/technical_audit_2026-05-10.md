# Elephant Rock Research Platform — Deep-Dive Technical Audit

**Date:** 2026-05-10
**Auditor:** ivory-wolf (Lead Programmer)
**Scope:** Full codebase — 365 backend files, 188 frontend files, 107,958 LOC
**Test Suite:** 2,480 tests collected

---

## 1. Executive Summary

Elephant Rock is an **AI-powered research pipeline platform** that automates the entire academic research lifecycle: literature discovery → gap identification → idea generation → proposal synthesis → export. A user enters a research topic, waits 20–45 minutes, and receives a structured research proposal with novelty scoring, feasibility assessment, full methodology, evaluation plans, and real citations.

### Scale

| Metric | Count |
|:-------|:------|
| Backend source files | 365 (.py) |
| Backend source LOC | 50,057 |
| Backend test files | 302 |
| Backend test LOC | 37,626 |
| Frontend source files | 188 (.ts/.tsx) |
| Frontend LOC | 20,275 |
| Total tests | 2,480 |
| API endpoints | ~118 (across 21 route files) |
| Database models | 11 tables |
| Pipeline packages | 38 |
| Config fields | 258 |
| Frontend pages | 20 |
| Frontend components | 83 |

### Architecture Verdict

The platform is **functionally complete** and **architecturally ambitious** — it implements 38 pipeline subsystems, 4 selectable strategies, a plugin system, an autonomous mode, and a full React frontend. The codebase shows rapid iterative development (140+ batches, ~354+ git commits) with strong test coverage (2,480 tests).

**The core risk is the orchestrator**: at 2,037 lines with 40+ methods and 25 `_init_*` methods, it is a God Object that has accumulated every feature as a private member. This is the #1 technical debt item and the single biggest threat to maintainability.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                      │
│  20 pages · 83 components · Vite · React Router · TanStack  │
│  Query · Tailwind · Radix UI · i18n (9 languages)           │
└──────────────┬──────────────────────────────────────────────┘
               │ REST API (/api/v1/) + WebSocket
┌──────────────▼──────────────────────────────────────────────┐
│                     API LAYER (FastAPI)                       │
│  21 route modules · 118 endpoints · JWT auth · CORS · Rate   │
│  limiting · SSE streaming · OpenAPI docs                      │
└──────────────┬──────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│                  PIPELINE ORCHESTRATOR (2,037 LOC)            │
│  10-stage pipeline · 4 strategies · retry logic · cost       │
│  tracking · stage callback · integration service              │
└──────┬───┬───┬───┬───┬───┬───┬───┬───┬───┬─────────────────┘
       │   │   │   │   │   │   │   │   │   │
  ┌────▼───▼───▼───▼───▼───▼───▼───▼───▼───▼────────────────┐
  │              38 PIPELINE SUBSYSTEMS                        │
  │  literature · ingestion · gap_analysis · generation ·      │
  │  novelty · feasibility · evaluation · synthesis ·          │
  │  claims · wiki · curation · verification · memory ·        │
  │  knowledge · compaction · reasoning · safety · agents ·    │
  │  negotiation · planning · reflection · metacognition ·     │
  │  governance · autonomy · skills · sandboxing · export ·    │
  │  streaming · observability · context · adaptation ·         │
  │  experiment · journal · tools · session · tracing          │
  └──────────────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│                   PROVIDER LAYER                             │
│  Anthropic · OpenAI · Gemini · Ollama · LiteLLM · LM Studio  │
│  Task router · Cost tracker · Token counter                  │
└──────────────┬──────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│                    DATA LAYER                                │
│  SQLite (SQLAlchemy) · ChromaDB (embeddings) · BM25          │
│  11 tables · 7 migrations · Alembic                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Module-by-Module Breakdown

### 3.1 Pipeline Orchestrator (`backend/pipeline/orchestrator.py` — 2,037 LOC)

**The central nervous system.** This is the single most critical — and most problematic — file in the codebase.

**What it does:**
- Defines `_STAGE_ORDER` (10 stages: literature_search → ingestion → gap_analysis → idea_generation → novelty_checking → feasibility_scoring → mechanical_metrics → proposal_synthesis → proposal_deepening → export)
- `__init__` accepts a provider, settings, strategy, and stage callback
- Contains 25 `_init_*` methods that conditionally initialize subsystems based on config flags
- `run()` executes the full pipeline (lines 965–1478 = **513 lines**)
- `resume()` supports resuming from a specific stage
- `autonomous_cycle()` implements the autonomous research mode

**Critical metrics:**

| Metric | Value | Assessment |
|:-------|:------|:-----------|
| Total lines | 2,037 | 🔴 Too large for a single class |
| Methods | 40+ | 🔴 God Object territory |
| `_init_*` methods | 25 | 🔴 Constructor does too much |
| `run()` method | 513 lines | 🔴 Should be decomposed |
| Dependencies | ~30 subsystems | 🔴 Tight coupling |

**Key insight:** Every feature added since Phase 6 has been grafted onto this class as another `_init_*` method. The orchestrator knows about memory, governance, autonomy, sandboxing, observability, metacognition, MCP, context management, streaming, consolidation, adaptation, graph RAG, tool discovery, negotiation, and session management — all as private members. This violates the Single Responsibility Principle at an extreme level.

### 3.2 Pipeline Stages (`backend/pipeline/stages.py` — 1,044 LOC)

Defines `PipelineStage`, `StageContext`, and concrete stage implementations for each of the 10 pipeline stages. Each stage wraps a specific pipeline module and handles error recovery, timing, and logging.

**Assessment:** Well-structured. The stage abstraction is clean — each stage is independently testable and the `StageContext` carries cross-stage data. However, at 1,044 lines it's approaching the threshold where decomposition would help.

### 3.3 Proposal Synthesizer (`backend/pipeline/synthesis/proposal_synthesizer.py` — 681 LOC)

The most complex stage. Generates full research proposals from ideas by:
1. Building a prompt with idea, gaps, papers, and evaluation data
2. Calling the LLM in free-text mode (not structured_output — this was a critical fix)
3. Parsing the response into sections
4. Verifying references against the actual corpus
5. Sanitizing fabricated citations with `[Citation needed]`

**Key design decision:** Uses free-text `complete()` instead of `structured_output` because JSON schema enforcement forced the LLM into producing 4-field stubs. The free-text approach with section parsing produces 25K+ character proposals.

**Assessment:** Solid implementation. The reference verification and citation sanitization are security-critical features that work well.

### 3.4 Gap Analyzer (`backend/pipeline/gap_analysis/gap_analyzer.py` — ~200 LOC)

Takes ingested papers and identifies research gaps using LLM analysis with cluster-aware formatting. Outputs structured `ResearchGap` objects with descriptions, evidence, and cluster assignments.

**Notable:** Uses local LM Studio (qwen3-4b) for cost-effective gap detection. Had a bug with cluster strings vs ints that was fixed with regex normalization.

### 3.5 Literature Search (`backend/pipeline/literature/` — 4 modules)

- **`search_service.py`** — Orchestrates multi-source search with recursive depth
- **`semantic_scholar.py`** — Semantic Scholar API integration
- **`openalex_source.py`** — OpenAlex API integration
- **`crossref_source.py`** — CrossRef API integration

All three external API sources read their base URLs from settings (externalized in BATCH-138). The `search_service` supports recursive search (following citations) up to configurable depth.

### 3.6 Claims System (`backend/pipeline/claims/` — 7 modules)

Phase 9 structured knowledge layer:
- **`extractor.py`** — LLM-based claim extraction from papers
- **`store.py`** — SQLAlchemy persistence with keyword search
- **`connection_agent.py`** — Finds relationships between papers
- **`contradiction/detector.py`** — Detects contradictory claims
- **`method_problem.py`** — Identifies method×dataset gaps
- **`study_designer.py`** — Generates experimental designs
- **`models.py`** — 5 claim types, 20+ fields

**Assessment:** The most architecturally sound new addition. Clean separation of concerns, LLM-backed reasoning (not heuristics), and the store provides proper CRUD + search.

### 3.7 Wiki System (`backend/pipeline/wiki/` — 3 modules)

- **`generator.py`** — Generates structured wiki entries from papers
- **`verifier.py`** — Source-anchored quote verification + TrustTier system
- **`models.py`** — 30-field WikiEntry dataclass

**TrustTier** is a 5-level hierarchy: UNVERIFIED → LOW → MEDIUM → HIGH → VERY_HIGH. The verifier requires LLM to provide verbatim `supporting_quote` and verifies via fuzzy SequenceMatcher (0.85 threshold).

**Assessment:** Strong quality assurance layer. The staged confidence model is well-designed.

### 3.8 Knowledge & Retrieval (`backend/pipeline/knowledge/` — 9 modules)

- **`vector_store.py`** — ChromaDB-backed semantic search
- **`embedding_providers.py`** — OpenAI, Gemini, Ollama embedding providers
- **`graph.py`** — Knowledge graph construction
- **`library.py`** — Paper library management
- **`library_indexer.py`** — Indexes papers into vector store
- **`relationship_extractor.py`** — Extracts relationships between concepts

**Assessment:** The dual BM25 + semantic search hybrid is well-implemented. The knowledge graph module is present but lightly used.

### 3.9 Compaction System (`backend/pipeline/compaction/` — 7 modules)

Manages context window budgets:
- **`budget_manager.py`** — Per-stage token budgets (now settings-driven)
- **`window_manager.py`** — Checks and triggers compression
- **`paper_selector.py`** — Selects papers within budget
- **`model_profiles.py`** — Reference table of model context sizes

**Assessment:** Essential for long pipelines. The token budget system prevents context overflow and degrades gracefully.

### 3.10 Evaluation Framework (`backend/pipeline/evaluation/` — 8 modules)

- **`quality_gate.py`** — Configurable pass/fail thresholds per dimension
- **`mechanical_metrics.py`** — Automated quality scoring
- **`geval.py`** — G-Eval style LLM-based evaluation
- **`plan_generator.py`** — Generates evaluation plans for proposals
- **`proposal_evaluator.py`** — Pipeline-level quality assessment

**Assessment:** Comprehensive. The quality gate with per-dimension thresholds, weights, and required dimensions is production-grade.

### 3.11 Frontend (`frontend/src/` — 188 files, 20,275 LOC)

**Technology stack:** React 18 + TypeScript + Vite + TanStack Query + Tailwind CSS + Radix UI + React Router + i18next (9 languages)

**Pages (20):**

| Page | Lines | Purpose |
|:-----|:------|:--------|
| `run-detail.tsx` | 398 | Live pipeline monitoring with auto-refetch |
| `idea-detail.tsx` | 383 | Full proposal display with sections |
| `pipeline-new.tsx` | 341 | Pipeline configuration with strategy selector |
| `autonomous.tsx` | 328 | Autonomous research mode |
| `settings.tsx` | 317 | Global settings management |
| `gaps-explorer.tsx` | 274 | Research gap browsing with filters |
| `dashboard.tsx` | 240 | Overview with stats and recent items |
| `ideas-browser.tsx` | 230 | Idea browsing with score badges |

**Assessment:** The frontend is well-structured with proper lazy loading, TypeScript types, API client abstraction, and i18n support. The run-detail page with live 3-second polling is the most complex UI component.

### 3.12 API Layer (`backend/api/` — 21 route files, ~4,000 LOC)

| Route File | Endpoints | Lines | Key Operations |
|:-----------|:----------|:------|:---------------|
| `pipeline.py` | 33 | 977 | Run CRUD, stage control, progress, autonomous |
| `gaps.py` | 12 | 477 | Gap CRUD, feedback, clustering, canonical |
| `ideas.py` | 4 | 293 | Idea CRUD, refine, feedback |
| `exports.py` | 5 | 292 | Multi-format export |
| `auth.py` | 6 | 233 | Register, login, forgot-password, reset |
| `collaboration.py` | 4 | 208 | Comments, sharing |
| `recombination.py` | 4 | 213 | Idea recombination |
| `knowledge_graph.py` | 8 | 235 | Graph CRUD, visualization |
| `knowledge.py` | 4 | 196 | Search, upload, library |
| `notifications.py` | 5 | 187 | List, mark-read, read-all, stream |

**Assessment:** The API is well-organized with clear separation. The `pipeline.py` at 977 lines is the largest route file and handles 33 endpoints — this is approaching the size where splitting would help (e.g., separating pipeline runs from autonomous mode).

### 3.13 Provider Layer (`backend/providers/` — 11 files)

6 LLM providers with a unified `LLMProvider` base class:

```
LLMProvider (ABC)
├── AnthropicProvider  — z.ai proxy or direct
├── OpenAIProvider     — OpenAI API
├── GeminiProvider     — Google Gemini
├── OllamaProvider     — Local Ollama
├── LiteLLMProvider    — Universal via litellm
└── StageWrapper       — Wraps provider with stage-specific config
```

**Model routing:** Task-specific routing (BATCH-78):
- Thinking tasks (gap analysis, novelty, feasibility) → Local LM Studio
- Generation tasks (synthesis, deepening) → Cloud LLM

**Assessment:** Clean abstraction. The `StageWrapper` pattern for per-stage configuration is elegant. The `task_router.py` for cost-based routing adds a second dimension of flexibility.

### 3.14 Data Layer (`backend/db/` — 3 files)

**Models (11 tables):**

| Table | Purpose | Key Fields |
|:------|:--------|:-----------|
| `users` | Auth | username, email, hashed_password, role |
| `papers` | Literature | title, authors, abstract, doi, year |
| `ideas` | Generated ideas | title, domain, novelty_score, feasibility_score |
| `proposals` | Full proposals | content (TEXT), word_count |
| `pipeline_runs` | Run history | domain, strategy, status, stage_data (JSON) |
| `comments` | Collaboration | body, user_id |
| `shared_ideas` | Sharing | token, expires_at |
| `notifications` | Alerts | type, title, message, user_id |
| `research_gaps` | Identified gaps | description, evidence, cluster_id |
| `research_claims` | Extracted claims | claim_type, source_paper_id, 22 columns |
| `experiment_results` | Experiments | idea_id, results (JSON) |

**Assessment:** SQLite is appropriate for single-user/research use. The JSON columns for `stage_data` and `results` provide schema flexibility but sacrifice queryability. No migration reversions exist.

---

## 4. Pipeline Data Flow

```
User Input: Research Domain
       │
       ▼
┌──────────────────┐     ┌──────────────┐
│ literature_search │────▸│  ingestion   │  (Semantic Scholar, OpenAlex, CrossRef)
│ (multi-source)    │     │ (embeddings) │  → papers[] with embeddings
└──────────────────┘     └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │ gap_analysis  │  (LLM cluster-aware analysis)
                         │ (local LM)    │  → gaps[] with cluster assignments
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │idea_generation│  (LLM ideation + tree search)
                         │               │  → ideas[] with novelty scores
                         └──────┬───────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
             ┌──────────┐ ┌──────────┐ ┌────────────┐
             │ novelty  │ │feasibility│ │ mechanical │
             │ checking │ │ scoring  │ │  metrics   │
             │(local LM)│ │(local LM)│ │            │
             └──────────┘ └──────────┘ └────────────┘
                    │           │           │
                    └───────────┼───────────┘
                                │
                         ┌──────▼───────┐
                         │proposal_     │  (LLM synthesis with reference
                         │ synthesis    │   verification + citation sanitization)
                         │ (cloud LLM)  │  → proposals{} with full sections
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │ proposal_    │  (LLM deepening — architecture,
                         │ deepening    │   failure modes, toy examples)
                         │ (cloud LLM)  │
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │    export    │  (Markdown, LaTeX, BibTeX, PDF)
                         └──────────────┘
```

**Typical timing (deep_research strategy):**

| Stage | Time | Model |
|:------|:-----|:------|
| literature_search | 7s | API calls |
| ingestion | 8 min | Cloud LLM (summarization) |
| gap_analysis | 23s | Local LM Studio |
| idea_generation | 5 min | Cloud LLM |
| novelty_checking | 5s | Local LM Studio |
| feasibility_scoring | 4s | Local LM Studio |
| proposal_synthesis | 6 min | Cloud LLM |
| proposal_deepening | 1.5 min | Cloud LLM |
| **Total** | **~21 min** | Hybrid |

---

## 5. Identified Bottlenecks

### BOTTLENECK-01: Orchestrator God Object (Severity: 🔴 CRITICAL)

**File:** `backend/pipeline/orchestrator.py` (2,037 LOC)
**Impact:** Every new feature touches this file. Every test needs to mock 25+ subsystems.

The orchestrator has 25 `_init_*` methods, each initializing a different subsystem. The `__init__` method calls all of them, creating tight coupling. The `run()` method is 513 lines and handles every stage transition, retry, persistence, and callback.

**Recommended fix:** Extract each subsystem into an independent service. The orchestrator should only coordinate, not own.

### BOTTLENECK-02: Sequential Ingestion (Severity: 🟡 HIGH)

**File:** `backend/pipeline/ingestion/scheduler.py`
**Impact:** Ingestion accounts for ~40% of total pipeline runtime.

Paper summarization is sequential — each paper calls the cloud LLM one at a time. With 36 papers and 10s per call, this takes 6+ minutes.

**Recommended fix:** Batch processing with `asyncio.gather()` and rate-limit-aware concurrency (5-10 concurrent calls).

### BOTTLENECK-03: Pipeline Route File Size (Severity: 🟡 HIGH)

**File:** `backend/api/routes/pipeline.py` (977 LOC, 33 endpoints)
**Impact:** Hard to navigate, test, and maintain.

**Recommended fix:** Split into `pipeline_runs.py`, `pipeline_autonomous.py`, `pipeline_progress.py`, `pipeline_export.py`.

### BOTTLENECK-04: SQLite for Production (Severity: 🟡 MEDIUM)

**File:** `backend/db/database.py`
**Impact:** Single-writer lock limits concurrent pipeline runs. No built-in replication.

**Mitigation:** Appropriate for current single-user research tool. Would need PostgreSQL for multi-user deployment.

### BOTTLENECK-05: No Streaming Proposal Synthesis (Severity: 🟢 LOW)

**File:** `backend/pipeline/synthesis/proposal_synthesizer.py`
**Impact:** Users wait 6+ minutes with no feedback during synthesis.

**Recommended fix:** Stream section-by-section generation with progress callbacks.

---

## 6. Technical Debt Inventory

### DEBT-01: God Object Orchestrator (CRITICAL)
- 2,037 lines, 40+ methods, 25 subsystem dependencies
- Every feature since Phase 6 grafted onto this class
- Risk: Any change to any subsystem requires modifying the orchestrator

### DEBT-02: Stale `_STAGE_ORDER` Coupling (HIGH)
- `_STAGE_ORDER` is a class-level list that must be updated manually when stages change
- `strategies/presets.py` must mirror it exactly (DEC-003)
- Strategy stage skip logic depends on string matching
- Risk: Adding/removing a stage requires changes in 4+ files

### DEBT-03: Inconsistent Error Handling (MEDIUM)
- Some modules use custom `APIError` subclasses
- Others raise raw `ValueError` or `RuntimeError`
- Pipeline stages silently catch and log exceptions (non-blocking per HB-01 pattern)
- Risk: Errors in non-critical subsystems can be silently swallowed

### DEBT-04: JSON Column Overuse (MEDIUM)
- `pipeline_runs.stage_data` stores arbitrary JSON
- `experiment_results.results` stores arbitrary JSON
- No schema validation on these columns
- Risk: Invalid JSON shapes can break frontend parsing

### DEBT-05: Mixed Sync/Async Patterns (MEDIUM)
- `startup()` is `async def` but uses `@app.on_event("startup")` (deprecated)
- Some pipeline modules use `asyncio.run()` in tests
- Provider `complete()` is async but some callers wrap it in `asyncio.run()`
- Risk: Event loop conflicts in concurrent environments

### DEBT-06: Frontend State Management Fragmentation (LOW)
- Auth state in `auth-context.tsx`
- Settings in `settings-context.tsx`
- Pipeline state split between React Query cache and SSE/polling hooks
- No global state store (Redux/Zustand)
- Risk: State inconsistencies between pages

### DEBT-07: Test Infrastructure Fragility (LOW)
- 196+ `trio` mode tests fail because `trio` is not installed
- `pytest.ini` has `-p no:asyncio` but some tests import `asyncio`
- Mock patches target different import paths inconsistently
- Risk: False negatives in CI

### DEBT-08: API Route Trailing Slash Sensitivity (LOW)
- FastAPI default `redirect_slashes=True` causes 307 redirects for routes without trailing slashes
- Frontend works because `fetch` follows redirects
- External API clients need `-L` flag or trailing slashes
- Risk: Confusion for API consumers

### DEBT-09: Configuration Field Proliferation (LOW)
- 258 config fields in `config.py`
- Many are feature flags for subsystems that may never be used
- No grouping or documentation within the file
- Risk: Configuration drift, unused settings

### DEBT-10: Deprecated FastAPI Patterns (LOW)
- `@app.on_event("startup")` is deprecated in favor of lifespan handlers
- `on_event("startup")` triggers deprecation warnings in tests
- Risk: Breaking changes in future FastAPI versions

---

## 7. Security Posture

### Strengths ✅

| Feature | Status | Implementation |
|:--------|:-------|:---------------|
| `.env` not in git | ✅ Clean | `git rm --cached` (BATCH-137) |
| JWT auth | ✅ Working | HS256 with 24h expiry |
| CORS configuration | ✅ Hardened | `EROCK_ENV` toggle (BATCH-140) |
| Production startup guard | ✅ Fatal on default JWT | RuntimeError in production (BATCH-140) |
| API key validation | ✅ Per-provider | Provider factory checks keys |
| Citation sanitization | ✅ Active | `[Citation needed]` for unverifiable refs |
| Rate limiting | ✅ 60/min | SlowAPI integration |
| Notification user scoping | ✅ Per-user | `user_id` filtering (BATCH-137) |
| Forgot password | ✅ Secure | Token-based reset with email enumeration prevention |

### Remaining Gaps ⚠️

| Gap | Severity | Description |
|:----|:---------|:------------|
| No HTTPS enforcement | MEDIUM | No TLS configuration for production deployment |
| No audit logging | MEDIUM | Sensitive operations (login, export) not logged |
| No input sanitization on domain | LOW | Pipeline accepts arbitrary strings as research domains |
| No CSP headers | LOW | No Content-Security-Policy middleware |
| WebSocket auth | LOW | WS handler has its own auth check but no rate limiting |

---

## 8. Test Coverage Assessment

| Category | Count | Coverage |
|:---------|:------|:---------|
| API route tests | ~184 | Good — all major endpoints covered |
| Pipeline unit tests | ~800+ | Good — all stages and subsystems |
| Frontend component tests | ~63 | Moderate — key components covered |
| Integration tests | ~50 | Moderate — smoke tests exist |
| E2E tests | ~10 | Low — manual browser testing only |

**Test-to-code ratio:** 37,626 test LOC / 50,057 source LOC = **0.75** — this is strong. Industry average is 0.3–0.5.

**Gaps:**
- No load/performance tests
- No security penetration tests
- No database migration rollback tests
- Frontend test coverage is lighter than backend

---

## 9. Documentation Quality

| Document | Exists | Quality | Lines |
|:---------|:-------|:--------|:------|
| README.md | ✅ | Good | ~200 |
| CHANGELOG.md | ✅ | Good | 140+ entries |
| STATE.md | ✅ | Good | 250+ |
| AIV Framework docs | ✅ | Excellent | 1,940 |
| API docs (OpenAPI) | ✅ | Auto-generated | FastAPI /docs |
| Inline code comments | ✅ | Adequate | ~5% of source |
| Architecture diagrams | ❌ | Missing | None |
| Deployment guide | ❌ | Missing | None |
| Contributing guide | ❌ | Missing | None |

**Assessment:** The AIV framework documentation is world-class — comprehensive, versioned, and enforced. The operational documentation (README, CHANGELOG, STATE.md) is solid. The gap is in architecture documentation — there are no system diagrams, deployment runbooks, or contributor guides. A new developer would need to read 2,037 lines of orchestrator code to understand the pipeline flow.

---

## 10. Recommendations (Priority Order)

### Immediate (1-2 days)

1. **Decompose the Orchestrator** — Extract `_init_*` methods into a `SubsystemRegistry` pattern. The orchestrator should be ~500 lines, delegating initialization to a builder.

2. **Parallelize Ingestion** — Use `asyncio.gather()` with semaphore-bounded concurrency (5-10 simultaneous) for paper summarization. Expected improvement: 8 min → 2-3 min.

3. **Split `pipeline.py` route file** — Break 977 lines into 4 focused route modules.

### Short-term (1 week)

4. **Add architecture documentation** — Create `docs/architecture.md` with system diagrams, data flow, and deployment topology.

5. **Replace deprecated `on_event`** — Migrate to FastAPI lifespan handler pattern.

6. **Add CSP and security headers middleware** — Standard production hardening.

### Medium-term (1 month)

7. **Introduce PostgreSQL option** — Add async SQLAlchemy with `asyncpg` driver for multi-user scenarios.

8. **Add streaming synthesis** — Stream proposal sections as they're generated.

9. **Consolidate feature flags** — Audit 258 config fields; remove unused ones, document the rest.

10. **Add load testing** — Establish performance baselines for concurrent pipeline runs.

---

## Appendix A: File Size Heatmap

**Backend files > 500 LOC (source only):**

| File | Lines | Role |
|:-----|:------|:-----|
| `pipeline/orchestrator.py` | 2,037 | 🔴 Pipeline coordinator |
| `pipeline/stages.py` | 1,044 | 🟡 Stage definitions |
| `api/routes/pipeline.py` | 977 | 🟡 API routes |
| `pipeline/synthesis/proposal_synthesizer.py` | 681 | Stage implementation |
| `pipeline/generation/dag_executor.py` | 650 | DAG execution |
| `pipeline/persistence.py` | 532 | Data persistence |

**Frontend files > 300 LOC:**

| File | Lines | Role |
|:-----|:------|:-----|
| `pages/run-detail.tsx` | 398 | Live monitoring |
| `pages/idea-detail.tsx` | 383 | Proposal display |
| `pages/pipeline-new.tsx` | 341 | Pipeline config |
| `pages/autonomous.tsx` | 328 | Autonomous mode |
| `pages/settings.tsx` | 317 | Settings |
| `pages/gaps-explorer.tsx` | 274 | Gap browsing |

---

*End of Technical Audit — ivory-wolf, 2026-05-10*
