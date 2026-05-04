# Elephant Rock: Next-Phase Execution Plan v5

**Plan Version:** v5  
**Date:** 2026-05-04  
**Status:** DRAFT — awaiting approval  
**Context:** Post-BATCH-59. All prior roadmaps CLOSED. User wants ALL deferred items included.

---

## Current State

| Metric | Value |
|--------|-------|
| Git commits | 193+ |
| Backend files | 498 Python |
| Frontend files | 179 TS/TSX |
| Backend tests | 148 passing |
| Frontend tests | 71 failing (Sentry env) |
| DB: Ideas | 73 |
| DB: Gaps | 72 |
| DB: Papers | 697 |
| DB: Proposals | 37 |
| Pipeline Runs | 42 |
| Research papers | 2 |

---

## Phase Overview — 14 Batches (BATCH-60 → BATCH-73)

### Workstream 1: PIPELINE RELIABILITY (BATCH-60, 61)
### Workstream 2: TREE SEARCH (BATCH-62, 63)
### Workstream 3: MECHANICAL METRICS + CROSS-RUN (BATCH-64, 65)
### Workstream 4: REAL EXPERIMENT EXECUTION — AIDER (BATCH-66)
### Workstream 5: UMAP/HDBSCAN CLUSTERING (BATCH-67)
### Workstream 6: SEMANTIC SCHOLAR API KEY HANDLING (BATCH-68)
### Workstream 7: WEBSOCKET REAL-TIME (BATCH-69)
### Workstream 8: PLUGIN MARKETPLACE (BATCH-70)
### Workstream 9: i18n EXPANSION (BATCH-71)
### Workstream 10: PRODUCTION + VERIFICATION (BATCH-72, 73)

---

## BATCH-60: Frontend Test Stabilization + Sentry Config

**Priority:** HIGH | **Effort:** Small

### TASK-01: Fix Sentry import in test environment
- Add `@sentry/react` mock to `frontend/vitest.config.ts`
- Mock `initSentry()` as no-op in test env
- **Deliverable:** All 339 frontend tests pass

### TASK-02: Fix Semantic Scholar rate limit handling
- Add exponential backoff with jitter for 429 responses
- Add `S2_API_KEY` configuration guidance in `.env.example`
- Queue retry with 30s delay instead of silent skip
- **Deliverable:** `backend/pipeline/literature/semantic_scholar.py` with retry logic

---

## BATCH-61: Pipeline End-to-End Reliability

**Priority:** HIGH | **Effort:** Medium

### TASK-01: Per-proposal timeout with graceful continuation
- Wrap each proposal synthesis in `asyncio.wait_for()` (120s timeout)
- On timeout: log, save partial, continue to next proposal
- **Deliverable:** `backend/pipeline/synthesis/proposal_synthesizer.py` updated

### TASK-02: Pipeline stage persistence + resume
- Save ideas/gaps to DB immediately after generation
- On resume: skip already-completed stages
- Add `--resume RUN_ID` CLI flag
- **Deliverable:** Orchestrator + CLI resume support

---

## BATCH-62: Tree Search Architecture (Part 1)

**Priority:** CRITICAL | **Effort:** Large

### TASK-01: TreeSearchEngine with beam search
- New: `backend/pipeline/generation/tree_search.py` (~400 lines)
- Beam search: expand N candidates → score → prune to K → repeat D levels
- Configurable: beam_width=3, max_depth=3, ideas_per_node=5
- **Deliverable:** TreeSearchEngine class

### TASK-02: Idea recombination operator
- At each tree node: optionally recombine 2 parent ideas into child
- Google showed 44% of recombinations beat both parents
- **Deliverable:** Recombination logic in TreeSearchEngine

---

## BATCH-63: Tree Search Architecture (Part 2)

**Priority:** CRITICAL | **Effort:** Large

### TASK-01: Pipeline integration — TreeSearchStage
- New stage replacing IdeaGenerationStage when `tree_of_thought_enabled=True`
- Ideator agent at each node, Critic/Refiner at pruning step
- Borda tournament on final candidate set
- **Deliverable:** `TreeSearchStage` in stages.py

### TASK-02: Frontend tree visualization
- New component: `TreeVisualization` with interactive node exploration
- Display on Run Detail page when tree search was used
- **Deliverable:** `frontend/src/components/pipeline/tree-visualization.tsx`

---

## BATCH-64: Mechanical Quality Metrics

**Priority:** HIGH | **Effort:** Medium

### TASK-01: Mechanical metric calculators
- New: `backend/pipeline/evaluation/mechanical_metrics.py` (~300 lines)
- Metrics: reference uniqueness, gap coverage %, citation density, method specificity, prior art distance
- **Deliverable:** MechanicalMetricsCalculator class

### TASK-02: Scoring integration + frontend display
- Composite: 40% LLM + 30% mechanical + 30% novelty/feasibility
- Display metric breakdown on idea detail page
- **Deliverable:** Scoring integration + frontend UI

---

## BATCH-65: Cross-Run Idea Recombination

**Priority:** MEDIUM | **Effort:** Medium

### TASK-01: Method DNA extraction
- Extract structured "method DNA" from top-scoring ideas
- New column: `method_dna` JSON on Idea model
- **Deliverable:** `backend/pipeline/generation/method_dna.py`

### TASK-02: Cross-run recombination API + UI
- New endpoint: `POST /recombination/propose` (takes 2+ run IDs)
- New page: recombination wizard in frontend
- **Deliverable:** API route + frontend page

---

## BATCH-66: Real Experiment Execution — Aider Integration

**Priority:** HIGH | **Effort:** Large

### TASK-01: Experiment generation from ideas
- New: `backend/pipeline/experiment/experiment_generator.py`
- Given an idea (title, method, evaluation approach), generate Python experiment code
- Uses LLM to write: hypothesis test, baseline comparison, ablation study
- Security validation via existing SecurityValidator
- **Deliverable:** ExperimentGenerator class

### TASK-02: Aider-style code execution in sandbox
- Integrate with existing SandboxManager (Docker > Subprocess > Noop backends)
- Generate experiment → validate → execute → capture results
- Add results to idea detail page: "Experiment Results" tab
- New API: `POST /ideas/{id}/run-experiment`
- **Deliverable:** Full experiment lifecycle from idea to results

### TASK-03: Experiment results integration
- Store experiment output in DB (new table: `experiment_results`)
- Display stdout/stderr/plots on idea detail page
- Auto-feed results back into scoring (idea with positive experiment gets boost)
- **Deliverable:** DB table + frontend tab + scoring integration

---

## BATCH-67: UMAP/HDBSCAN for Better Clustering

**Priority:** MEDIUM | **Effort:** Medium

### TASK-01: Install and integrate UMAP + HDBSCAN
- `pip install umap-learn hdbscan` (or bundled alternatives)
- Update `backend/pipeline/gap_analysis/cluster_service.py`
- UMAP for dimensionality reduction (currently using first 2 dims)
- HDBSCAN for clustering (currently KMeans fallback)
- Add graceful fallback if packages unavailable
- **Deliverable:** Better clustering in gap analysis stage

### TASK-02: Cluster quality metrics
- Add silhouette score, Davies-Bouldin index reporting
- Display cluster quality on gap explorer page
- **Deliverable:** Quality metrics + frontend display

---

## BATCH-68: Semantic Scholar API Key Handling

**Priority:** MEDIUM | **Effort:** Small

### TASK-01: Improved API key configuration
- Clear `.env.example` instructions for `S2_API_KEY`
- Detect missing key at startup, log warning
- Add `/api/settings/academic-sources` endpoint showing key status
- **Deliverable:** Better S2 configuration experience

### TASK-02: Smart rate limit strategy
- Track remaining requests from S2 response headers
- Auto-throttle when approaching limit
- Prioritize queries by expected yield
- Cache previous search results for 24h to reduce API calls
- **Deliverable:** Smart rate limiting in SemanticScholarSource

---

## BATCH-69: WebSocket Real-Time Pipeline Updates

**Priority:** MEDIUM | **Effort:** Medium

### TASK-01: Wire pipeline stages to WebSocket broadcasts
- Existing `backend/api/ws.py` + `ConnectionManager` infrastructure
- Pipeline stage transitions broadcast to `pipeline:{run_id}` channel
- Stage start/complete/failed events with progress data
- **Deliverable:** Live pipeline progress via WebSocket

### TASK-02: Frontend WebSocket integration
- Update `usePipelineProgress` hook to use WebSocket (currently SSE polling)
- Real-time stage progress on Run Detail page
- Toast notifications on stage completion
- **Deliverable:** Live-updating run detail page

---

## BATCH-70: Plugin Marketplace

**Priority:** MEDIUM | **Effort:** Medium

### TASK-01: Backend plugin registry API
- New: `backend/api/routes/plugins.py` enhanced
- CRUD for plugins: register, list, install, uninstall
- Plugin metadata: name, version, author, description, capabilities
- Plugin verification (existing `plugin_verification_enabled`)
- **Deliverable:** Plugin registry API

### TASK-02: Frontend marketplace UI
- New page: Plugin Marketplace with browse/install/uninstall
- Plugin cards with ratings, download counts, compatibility
- Settings page integration for plugin management
- **Deliverable:** `frontend/src/pages/plugin-marketplace.tsx`

---

## BATCH-71: i18n Expansion (fr, de, ja, ko, pt, ar) + RTL

**Priority:** MEDIUM | **Effort:** Large

### TASK-01: Add 6 new language locales
- Generate `fr.json`, `de.json`, `ja.json`, `ko.json`, `pt.json`, `ar.json`
- Machine-translate existing en.json keys (200+ keys)
- Arabic requires full RTL mirroring of all UI strings
- Update `frontend/src/i18n/config.ts` with new locales
- **Deliverable:** 9 supported languages (en, zh, es, fr, de, ja, ko, pt, ar)

### TASK-02: RTL Layout Infrastructure
- Add `dir="rtl"` attribute propagation based on active locale
- CSS: flip flex directions, margins, paddings, text-align
- Use `[dir='rtl']` CSS selectors or logical properties (margin-inline-start)
- RTL-aware components: sidebar (flip), breadcrumbs (flip separators), forms
- Test every page in RTL mode
- **Deliverable:** Full RTL layout support for Arabic

### TASK-03: Language switcher UI
- Add language selector to sidebar footer + settings page
- Persist language preference in localStorage
- Native language names in dropdown (العربية, 中文, Español, etc.)
- Auto-detect browser language on first visit
- **Deliverable:** Language switcher with auto-detect

---

## BATCH-72: Docker Production Stack

**Priority:** MEDIUM | **Effort:** Medium

### TASK-01: Full-stack Docker Compose verification
- Backend + Frontend + nginx + ChromaDB
- Health checks, volume mounts, env injection
- **Deliverable:** Verified `docker-compose.yml` + `DOCKER.md`

### TASK-02: nginx reverse proxy
- Frontend: `/` → React build
- API: `/api/*` → FastAPI
- WebSocket: `/ws/*` → backend
- SSL termination placeholder
- **Deliverable:** Verified `nginx/nginx.conf`

---

## BATCH-73: Performance Benchmarking + Final Verification

**Priority:** LOW | **Effort:** Small

### TASK-01: API performance benchmarks
- All endpoints <500ms p95
- Identify N+1 query issues
- **Deliverable:** `docs/PERFORMANCE.md`

### TASK-02: Full E2E verification (Third UX Test)
- All pages screenshot
- Pipeline execution with tree search
- All new features verified
- **Deliverable:** Updated E2E test report

---

## Dependency Graph

```
BATCH-60 ──────────────────────────────────────────────┐
BATCH-61 ──────────────────────────────────────────────┤
BATCH-62 ──► BATCH-63                                  ├──► BATCH-73
BATCH-64 ──────────────────────────────────────────────┤
BATCH-65 ──────────────────────────────────────────────┤
BATCH-66 (Aider) ──────────────────────────────────────┤
BATCH-67 (UMAP) ───────────────────────────────────────┤
BATCH-68 (S2 API) ─────────────────────────────────────┤
BATCH-69 (WebSocket) ──────────────────────────────────┤
BATCH-70 (Plugins) ────────────────────────────────────┤
BATCH-71 (i18n) ───────────────────────────────────────┘
BATCH-72 (Docker) ─────────────────────────────────────┘
```

---

## Estimated Effort

| Batch | Tasks | Est. LOC | Time |
|-------|-------|----------|------|
| 60: Frontend+Sentry | 2 | ~200 | 30m |
| 61: Pipeline Reliability | 2 | ~400 | 45m |
| 62: Tree Search 1 | 2 | ~500 | 60m |
| 63: Tree Search 2 | 2 | ~400 | 45m |
| 64: Mechanical Metrics | 2 | ~500 | 45m |
| 65: Cross-Run Recombination | 2 | ~400 | 45m |
| **66: Aider Experiments** | **3** | **~800** | **90m** |
| **67: UMAP/HDBSCAN** | **2** | **~300** | **30m** |
| **68: S2 API Key** | **2** | **~300** | **30m** |
| **69: WebSocket** | **2** | **~400** | **45m** |
| **70: Plugin Marketplace** | **2** | **~500** | **45m** |
| **71: i18n + RTL (Arabic)** | **3** | **~900** | **60m** |
| 72: Docker Production | 2 | ~200 | 30m |
| 73: Final Verification | 2 | ~100 | 30m |
| **Total** | **30** | **~5,300** | **~9.5h** |

---

## Success Criteria

1. ✅ All frontend tests pass (339+)
2. ✅ Pipeline completes end-to-end without timeout
3. ✅ Tree search produces ideas ≥10% higher scores than linear
4. ✅ Mechanical metrics visible in frontend
5. ✅ Ideas can run real experiments in sandbox (Aider pattern)
6. ✅ UMAP/HDBSCAN clustering produces better gap clusters
7. ✅ Semantic Scholar smart rate limiting (no silent skips)
8. ✅ WebSocket real-time pipeline progress works
9. ✅ Plugin marketplace UI functional
10. ✅ 9 languages supported (en/zh/es/fr/de/ja/ko/pt/ar) with full RTL
11. ✅ Docker Compose starts full stack
12. ✅ All API endpoints <500ms p95
