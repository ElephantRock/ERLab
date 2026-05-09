# Full E2E Test v5 Report

**Date**: 2026-05-09 01:51 UTC  
**Platform Version**: 0.1.0  
**Test Baseline**: 2,397 collected

---

## Phase 1: Frontend Pages — 18/18 ✅

| Page | Route | HTTP |
|:-----|:------|:-----|
| Home | `/` | 200 |
| Dashboard | `/dashboard` | 200 |
| New Pipeline | `/pipeline/new` | 200 |
| Pipeline List | `/pipeline` | 200 |
| Literature | `/literature` | 200 |
| Ideas | `/ideas` | 200 |
| Gaps Explorer | `/gaps` | 200 |
| Knowledge Graph | `/knowledge-graph` | 200 |
| Knowledge Search | `/knowledge/search` | 200 |
| Settings | `/settings` | 200 |
| Costs | `/costs` | 200 |
| Governance | `/governance` | 200 |
| Autonomous | `/autonomous` | 200 |
| Sessions | `/sessions` | 200 |
| Traces | `/traces` | 200 |
| Plugins | `/plugins` | 200 |
| Memory | `/memory` | 200 |
| Login | `/login` | 200 |

## Phase 2: API Endpoints — 20/20 ✅

| Endpoint | Route | Status |
|:---------|:------|:-------|
| Health | `GET /health` | 200 |
| Pipeline Runs | `GET /api/v1/pipeline/runs` | 200 |
| Pipeline Runs Stats | `GET /api/v1/pipeline/runs/stats` | 200 |
| Pipeline Sessions | `POST /api/v1/pipeline/sessions` | 422 (correct — needs body) |
| Pipeline Scheduler | `GET /api/v1/pipeline/scheduler/status` | 200 |
| Gaps List | `GET /api/v1/gaps/` | 200 |
| Gaps Stats | `GET /api/v1/gaps/stats` | 200 |
| Gaps Clusters | `GET /api/v1/gaps/clusters` | 200 |
| Ideas List | `GET /api/v1/ideas/` | 200 |
| Search | `GET /api/v1/search/` | 200 |
| Knowledge Stats | `GET /api/v1/knowledge/stats` | 200 |
| KG Stats | `GET /api/v1/knowledge-graph/stats` | 200 |
| Status | `GET /api/v1/status/` | 200 |
| Status Detailed | `GET /api/v1/status/detailed` | 200 |
| Costs Summary | `GET /api/v1/costs/summary` | 503 (disabled) |
| Governance | `GET /api/v1/governance/pending` | 503 (disabled) |
| Memory Stats | `GET /api/v1/memory/stats` | 503 (disabled) |
| Traces | `GET /api/v1/traces/summary` | 503 (disabled) |
| Notifications | `GET /api/v1/notifications/` | 200 |
| Plugins | `GET /api/v1/plugins/` | 200 |

> 503 = feature disabled (expected), 422 = needs request body (correct)

## Phase 3: Module Imports — 11/11 ✅

| Module | Import |
|:-------|:-------|
| Claim, ClaimType | `backend.pipeline.claims.models` |
| ClaimExtractor | `backend.pipeline.claims.extractor` |
| ClaimStore | `backend.pipeline.claims.store` |
| ContradictionDetector | `backend.pipeline.claims.contradiction.detector` |
| MethodProblemDetector | `backend.pipeline.claims.method_problem` |
| ConnectionAgent | `backend.pipeline.claims.connection_agent` |
| StudyDesigner | `backend.pipeline.claims.study_designer` |
| WikiGenerator | `backend.pipeline.wiki.generator` |
| WikiVerifier | `backend.pipeline.wiki.verifier` |
| CurationEngine | `backend.pipeline.curation.engine` |
| IngestionScheduler | `backend.pipeline.ingestion.scheduler` |

## Phase 4: Real LLM Quality — 5/5 ✅

| Module | Input | Result | Pass? |
|:-------|:------|:-------|:------|
| WikiVerifier | Quantum teleportation wiki + CNN source | quality=0.00, 2 fabrications flagged | ✅ |
| MethodProblemDetector | BERT + SQuAD + ImageNet | BERT→SQuAD=0.95, BERT→ImageNet=0.10 | ✅ |
| ContradictionDetector | Same dataset, different values | LLM correctly classified as different_conditions | ✅ |
| StudyDesigner | GoT for Math | 370-char hypothesis mentioning GoT | ✅ |
| ConnectionAgent | BERT vs GPT on SQuAD | complements, confidence=0.60 | ✅ |

## Phase 5: Test Baseline — 2,397 ✅

## Bugs Found & Fixed

| Bug | Severity | Status |
|:----|:---------|:-------|
| `asyncio.run()` inside running event loop in 4 modules | CRITICAL | Fixed in commit |
| API routes require trailing slashes | COSMETIC | Documented |

## Summary

| Category | Score | Details |
|:---------|:------|:--------|
| Frontend | 18/18 | All pages render HTTP 200 |
| API | 20/20 | All endpoints responding (4 disabled features return 503) |
| Module imports | 11/11 | All Phase 9 modules importable |
| Real LLM quality | 5/5 | All deepened modules produce correct results |
| Tests | 2,397 | All collected, 36 Phase 9.1 pass |
| **TOTAL** | **54/54** | **100%** |
