# Elephant Rock: Next-Phase Execution Plan

**Plan Version:** v4  
**Date:** 2026-05-04  
**Status:** DRAFT — awaiting approval  
**Context:** Post-BATCH-59, all prior roadmaps (BATCH-07→57, BATCH-38→47, BATCH-48→53, BATCH-55→59) are CLOSED

---

## Current State Snapshot

| Metric | Value |
|--------|-------|
| Git commits | 193+ |
| Backend files | 498 Python |
| Frontend files | 179 TS/TSX |
| Backend tests | 148 passing |
| Frontend tests | 71 failing (Sentry env issue) |
| DB: Ideas | 73 |
| DB: Gaps | 72 |
| DB: Papers | 697 |
| DB: Proposals | 37 |
| DB: Pipeline Runs | 42 |
| Research papers | 2 published-quality |
| Study reports | 35 documents |

---

## Phase Overview

This plan addresses **4 workstreams** with **8 batches** (BATCH-60 through BATCH-67):

1. **PIPELINE RELIABILITY** — Fix remaining infrastructure issues so every pipeline run completes end-to-end
2. **TREE SEARCH ARCHITECTURE** — Implement the highest-priority competitive feature from Google's paper
3. **FRONTEND STABILITY** — Fix failing tests, improve the run experience
4. **PRODUCTION READINESS** — Docker, nginx, and deployment verification

---

## BATCH-60: Frontend Test Stabilization + Sentry Config

**Priority:** HIGH  
**Effort:** Small  
**Rationale:** 71/71 frontend tests fail due to missing Sentry module resolution in test environment. This is a trivial fix that restores the CI safety net.

### TASK-01: Fix Sentry import in test environment
- Add `@sentry/react` mock to `frontend/src/setupTests.ts` or `vitest.config.ts`
- Mock `initSentry()` as no-op in test env
- **Deliverable:** All frontend tests pass (target: 339 tests)

### TASK-02: Fix Semantic Scholar rate limit handling
- Add exponential backoff with jitter for 429 responses (currently logs warning and skips)
- Add `S2_API_KEY` configuration guidance in `.env.example`
- When rate-limited, don't silently skip — queue retry with 30s delay
- **Deliverable:** `backend/pipeline/literature/semantic_scholar.py` updated with retry logic

---

## BATCH-61: Pipeline End-to-End Reliability

**Priority:** HIGH  
**Effort:** Medium  
**Rationale:** Pipeline Run #42 produced 10 ideas but timed out during proposal synthesis (30 min). The circuit breaker and JSON repair helped, but proposal synthesis is still the bottleneck.

### TASK-01: Async proposal synthesis with timeout per proposal
- Wrap each proposal synthesis in `asyncio.wait_for()` with per-proposal timeout (120s)
- If one proposal times out, log and continue to next (don't block the entire batch)
- **Deliverable:** `backend/pipeline/synthesis/proposal_synthesizer.py` updated

### TASK-02: Pipeline progress persistence
- Save ideas and gaps to DB immediately after generation (before proposals)
- On resume/retry, skip stages that already completed
- Add `--resume RUN_ID` flag to CLI
- **Deliverable:** `backend/pipeline/orchestrator.py` + `backend/cli/main.py` updated

---

## BATCH-62: Tree Search Architecture (Part 1)

**Priority:** CRITICAL (highest-priority architectural change from Google paper)  
**Effort:** Large  
**Rationale:** Google's arXiv 2509.06503 proves LLM + Tree Search dramatically outperforms single calls. 40/87 methods beat all published approaches. Elephant Rock's linear Ideator→Critic→Refiner should become a branching tree search.

### TASK-01: Implement TreeSearchEngine
- New module: `backend/pipeline/generation/tree_search.py`
- Core algorithm: Beam search over idea space
  - Generate N candidate ideas (expand)
  - Score with mechanical metrics + LLM quality gate (evaluate)
  - Keep top-K by score (prune)
  - Repeat for D depth levels
- Configurable: beam_width (default 3), max_depth (default 3), ideas_per_node (default 5)
- **Deliverable:** `backend/pipeline/generation/tree_search.py` (new file, ~400 lines)

### TASK-02: Idea recombination operator
- At each tree node, allow "recombine" — take 2 parent ideas, generate child
- Google showed 44% of recombinations beat both parents
- Recombination prompt: "Given Idea A (method X) and Idea B (method Y), synthesize a novel approach combining the strengths of both"
- **Deliverable:** Recombination logic integrated into TreeSearchEngine

---

## BATCH-63: Tree Search Architecture (Part 2)

**Priority:** CRITICAL  
**Effort:** Large  
**Rationale:** Integration of tree search into the existing pipeline, replacing the linear Ideator→Critic→Refiner flow.

### TASK-01: Pipeline stage integration
- New stage: `TreeSearchStage` replacing `IdeaGenerationStage` when `tree_of_thought_enabled=True`
- Tree search runs the Ideator agent at each node
- Critic and Refiner agents evaluate at pruning step
- Borda tournament ranks final candidate set
- Backward-compatible: when tree search disabled, falls back to existing linear flow
- **Deliverable:** `backend/pipeline/stages.py` updated with `TreeSearchStage`

### TASK-02: Frontend tree visualization
- New component: `TreeVisualization` showing the search tree
- Display: node labels (idea titles), edge scores, pruning decisions
- Interactive: click nodes to see full idea details
- Show on Run Detail page when tree search was used
- **Deliverable:** `frontend/src/components/pipeline/tree-visualization.tsx`

---

## BATCH-64: Mechanical Quality Metrics

**Priority:** HIGH  
**Rationale:** Google's system uses ONLY mechanical metrics (WIS, mIoU, MAE). Elephant Rock currently relies on LLM-judged quality, which is subjective and variable. Adding mechanical metrics creates objective quality signals.

### TASK-01: Implement mechanical metric calculators
- Reference uniqueness: % of cited papers not previously cited in same domain
- Gap coverage: % of identified gaps addressed by an idea's method
- Citation density: average citations per supporting paper
- Method specificity: count of concrete, testable claims in proposed method
- Prior art distance: vector similarity between idea embedding and closest existing paper
- **Deliverable:** `backend/pipeline/evaluation/mechanical_metrics.py` (new file, ~300 lines)

### TASK-02: Integrate mechanical metrics into idea scoring
- Add mechanical metrics as input to the composite score
- Weight: 40% LLM judgment + 30% mechanical metrics + 30% novelty/feasibility
- Display mechanical metric breakdown on idea detail page
- **Deliverable:** Scoring integration + frontend display

---

## BATCH-65: Cross-Run Idea Recombination

**Priority:** MEDIUM  
**Rationale:** Ideas from Run 24 (Self-Learning) and Run 25 (Self-Improvement) could be recombined to produce novel hybrid approaches. Currently, each run is isolated.

### TASK-01: Method DNA extraction
- For each top-scoring idea, extract "method DNA": core technique, domain, evaluation approach
- Store as structured JSON on Idea model (new column: `method_dna`)
- **Deliverable:** `backend/pipeline/generation/method_dna.py` (new file)

### TASK-02: Cross-run recombination pipeline
- New API endpoint: `POST /recombination/propose`
- Takes 2+ run IDs, extracts top ideas from each, recombines
- Uses tree search recombination operator (from BATCH-62)
- Stores recombined ideas with `source_idea_ids` traceability
- **Deliverable:** `backend/api/routes/recombination.py` (new file)

---

## BATCH-66: Docker Production Stack

**Priority:** MEDIUM  
**Rationale:** BATCH-51 created Docker configs but never verified end-to-end. Production deployment requires verified Docker Compose with nginx.

### TASK-01: Docker Compose full-stack verification
- Verify `docker-compose.yml` builds and runs: backend + frontend + nginx + ChromaDB
- Health checks on all services
- Volume mounts for persistent data
- Environment variable injection
- **Deliverable:** Verified `docker-compose.yml` + `DOCKER.md`

### TASK-02: nginx reverse proxy configuration
- Frontend: serve React build on `/`
- Backend API: proxy `/api/*` to FastAPI
- WebSocket: proxy `/ws/*` to backend
- SSL termination placeholder
- **Deliverable:** `nginx/nginx.conf` verified working

---

## BATCH-67: Performance Benchmarking + Final Verification

**Priority:** LOW  
**Rationale:** Baseline performance numbers for production planning.

### TASK-01: API performance benchmarks
- Measure: Dashboard load, ideas list, gap explorer, pipeline run start
- Target: all API endpoints <500ms p95
- Identify N+1 query issues
- **Deliverable:** `docs/PERFORMANCE.md` with baseline numbers

### TASK-02: Full E2E verification
- Third full UX test: all pages, pipeline execution, tree search
- Screenshot all pages
- Verify all 8 batches work end-to-end
- **Deliverable:** Updated E2E test report

---

## Batch Dependency Graph

```
BATCH-60 (Frontend + Sentry)  ─────────────────────────────┐
BATCH-61 (Pipeline Reliability) ────────────────────────────┤
                                                             ├──► BATCH-67 (Final Verification)
BATCH-62 (Tree Search Part 1) ──► BATCH-63 (Tree Search 2) ─┤
BATCH-64 (Mechanical Metrics) ──────────────────────────────┤
BATCH-65 (Cross-Run Recombination) ─────────────────────────┘
BATCH-66 (Docker Production) ────────────────────────────────┘
```

Batches 60, 61, 62, 64, 65, 66 can run in parallel.  
BATCH-63 depends on BATCH-62.  
BATCH-67 depends on all others.

---

## Estimated Effort

| Batch | Tasks | Est. LOC | Est. Time |
|-------|-------|----------|-----------|
| BATCH-60 | 2 | ~200 | 30 min |
| BATCH-61 | 2 | ~400 | 45 min |
| BATCH-62 | 2 | ~500 | 60 min |
| BATCH-63 | 2 | ~400 | 45 min |
| BATCH-64 | 2 | ~500 | 45 min |
| BATCH-65 | 2 | ~400 | 45 min |
| BATCH-66 | 2 | ~200 | 30 min |
| BATCH-67 | 2 | ~100 | 30 min |
| **Total** | **16** | **~2,700** | **~5.5 hrs** |

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Tree search LLM cost explosion | Medium | Cap beam_width at 3, max_depth at 3 |
| Mechanical metrics not predictive | Low | Start with Google-proven metrics (uniqueness, coverage) |
| Frontend tests still fail after Sentry fix | Low | Check for other missing mocks |
| Docker networking issues | Medium | Test on clean Docker environment |
| Proposal synthesis still slow | Medium | Per-proposal timeout from BATCH-61 |

---

## Success Criteria

1. ✅ All frontend tests pass (339+)
2. ✅ Pipeline completes end-to-end without timeout (all 10 proposals)
3. ✅ Tree search produces ideas scoring ≥10% higher than linear Ideator
4. ✅ Mechanical metrics visible in frontend
5. ✅ Cross-run recombination produces at least 5 novel ideas
6. ✅ Docker Compose starts full stack with one command
7. ✅ All API endpoints respond <500ms p95

---

## What This Plan Does NOT Cover

These items are deferred to a future phase:
- Real experiment execution (Aider integration) — requires security review
- UMAP/HDBSCAN for better clustering — dependency installation issue
- Semantic Scholar API key — requires user to obtain key
- WebSocket real-time pipeline updates — infrastructure exists, needs testing
- Plugin marketplace — SDK docs done, marketplace UI deferred
- i18n expansion beyond en/zh/es — current 3 languages sufficient
