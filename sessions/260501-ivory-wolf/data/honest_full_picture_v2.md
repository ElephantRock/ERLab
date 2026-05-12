# Honest Full Picture — Post B172-B177 Remediation

**Date:** 2026-05-11  
**Assessor:** Lead Programmer (ivory-wolf)  
**Method:** Live API testing against running backend + codebase analysis  
**No second opinions. No padding. Just what is.**

---

## What Works (Verified Live)

### ✅ Backend API — 82 Registered Endpoints

The backend starts and serves 82 routes across 14 route groups. I tested these live:

| Endpoint | Status | Notes |
|:---------|:-------|:------|
| `GET /health` | 200 ✅ | Returns `{"status":"ok","version":"0.1.0"}` |
| `GET /api/v1/pipeline/runs` | 200 ✅ | Returns 115 historical runs with pagination |
| `GET /api/v1/pipeline/runs/detail/{id}` | 200 ✅ | Returns run config, stages, ideas, stage_report, stale flag |
| `GET /api/v1/pipeline/runs/stale` | 200 ✅ | Lists stuck "running" runs with age calculation |
| `POST /api/v1/pipeline/watchdog` | 200 ✅ | Found 2 stale runs, marked both as failed |
| `GET /api/v1/ideas/` | 200 ✅ | 131 ideas with pagination |
| `GET /api/v1/gaps/` | 200 ✅ | 245+ gaps with full descriptions |
| `GET /api/v1/search/knowledge/{domain}` | 200 ✅ | Returns paper/gap counts per domain |
| `GET /api/v1/knowledge-graph/stats` | 200 ✅ | 1,715 entities, 816 relationships |
| `GET /api/v1/knowledge-graph/entities` | 200 ✅ | Entity listing |
| `POST /api/v1/pipeline/run` | 200 ✅ | **After preflight fix** — starts pipeline, returns run_id |

### ✅ Pipeline Execution — Stages 0-1 Work

- **Literature search** (stage 0): Completes in ~74 seconds. Found papers from OpenAlex + arXiv.
- **Ingestion** (stage 1): Starts and processes papers. **Slow** — took 20+ minutes for "Test Domain" and appeared stuck. This is likely due to per-paper LLM summarization calls going through the cloud provider.

### ✅ Pipeline Wiring — 16/16 Stages Present

Verified by checkpoint file: all 16 stages appear in `_STAGE_ORDER` and the checkpoint JSON. The orchestrator constructs all 16 stage objects in `_build_stages()`.

### ✅ Preflight Validation — Works After Fix

The preflight correctly:
- Checks LLM provider reachability (makes a real `complete()` call)
- Blocks runs when provider is unreachable (503 response)
- Passes runs when provider is reachable (200 with preflight key)

### ✅ Watchdog — Works Correctly

Marked 2 stale runs as "failed" within seconds of calling `POST /watchdog`. Both runs had been stuck in "running" for 2+ hours.

### ✅ Stale Detection — Works

`GET /runs/stale` correctly identified 2 runs stuck in "running" status. The `stale: true/false` flag in run detail correctly distinguishes running (stale=true) from completed (stale=false).

### ✅ Data Accumulation — Substantial

- **1,275+ papers** ingested across 115 runs
- **245+ research gaps** identified
- **131 ideas** generated
- **68+ proposals** synthesized
- **1,715 KG entities** and 816 relationships
- **81 exported files** on disk

---

## What Doesn't Work (Verified Live)

### ❌ CRITICAL: Preflight Had Two Bugs Preventing ALL Pipeline Runs

**Bug 1:** `ProviderFactory` import — the preflight module imported a class that doesn't exist.  
**Bug 2:** `provider.complete("string")` — the API expects `messages: list[dict]`, not a plain string.  
**Impact:** No pipeline run could start. Every `POST /pipeline/run` returned 503.  
**Status:** Fixed in commit `513057f`.  
**Honest note:** B172's 26 tests all passed. B173's 21 tests all passed. Neither caught this because the tests mocked the provider. **2,849 tests did not catch a bug that prevented the pipeline from running at all.**

### ❌ CRITICAL: stage_report Not Persisted to Database

Run #116 (live test) shows `stage_report: []` in the API response despite B173 supposedly adding this. The checkpoint file tracks stages, but the `stage_report_json` column in the DB is not being written.  
**Root cause:** The orchestrator populates `result.stage_report` in memory but the persistence layer doesn't serialize it to the DB column.  
**Impact:** Users can't see which stages ran, which were skipped, or why. The entire B173 observability feature is invisible in the API.  
**Status:** Not fixed.

### ❌ CRITICAL: Ingestion Stage Is Extremely Slow

Ingestion took 20+ minutes for a "Test Domain" query that found ~30 papers. Each paper requires an LLM call for summarization, and these go to the cloud provider sequentially.  
**Impact:** The fast_scan strategy takes 25+ minutes instead of 5 minutes. The user waits with no visible progress.  
**Root cause:** Sequential per-paper LLM calls in ingestion. No batching, no parallelization.  
**Status:** Not fixed.

### ⚠️ HIGH: Trailing Slash Inconsistency

`GET /api/v1/ideas` returns 307 redirect. `GET /api/v1/ideas/` returns 200. FastAPI's redirect behavior means the frontend must always use trailing slashes. This was assessed as "not a bug" in P1-07 but it's still confusing.  
**Status:** Assessed, no fix planned.

### ⚠️ HIGH: novelty_score and feasibility_score Are Null for All Ideas

All 131 ideas in the database show `novelty_score: null` and `feasibility_score: null`. The scoring stages run but don't persist scores back to the idea records.  
**Impact:** The ideas browser shows no scores. Users can't sort or filter by quality.  
**Root cause:** Scores are stored in `result.novelty_reports` and `result.feasibility_reports` (dicts keyed by idea index) but never written back to the `ResearchIdea` DB rows.  
**Status:** Not fixed.

### ⚠️ HIGH: LM Studio Dependency for Gap Analysis

The pipeline routes gap analysis to local LM Studio (qwen3-4b). If LM Studio is down, gap analysis fails. The preflight check doesn't verify LM Studio connectivity — only the primary cloud provider.  
**Impact:** Pipeline starts, literature search succeeds, then gap analysis crashes. Run gets stuck or fails at stage 2.  
**Status:** Not fixed. Preflight only checks cloud provider.

### ⚠️ MEDIUM: S2 API Key Not Set

Semantic Scholar is excluded from searches to avoid 429 rate limiting. This means only OpenAlex and arXiv are used for literature search, missing the largest academic paper database.  
**Status:** Configuration issue. Set `S2_API_KEY` in `.env`.

---

## What's Structural (Code on Disk but Not Verified Live)

### 16 Pipeline Stages — Wired but Only 2 Tested Live

| Stage | Wired | Live-Tested | Notes |
|:------|:------|:------------|:------|
| 0. literature_search | ✅ | ✅ | 74s, found papers |
| 1. ingestion | ✅ | ⚠️ | Started but 20+ min, didn't complete during test |
| 2. gap_analysis | ✅ | ❌ | Never reached in live test |
| 3. gap_reflection | ✅ | ❌ | Depends on gap_analysis |
| 4. idea_generation | ✅ | ❌ | |
| 5. idea_reflection | ✅ | ❌ | |
| 6. novelty_checking | ✅ | ❌ | |
| 7. feasibility_scoring | ✅ | ❌ | |
| 8. mechanical_metrics | ✅ | ❌ | |
| 9. proposal_synthesis | ✅ | ❌ | |
| 10. adversarial_review | ✅ | ❌ | |
| 11. evaluation | ✅ | ❌ | |
| 12. paper_synthesis | ✅ | ❌ | |
| 13. citation_audit | ✅ | ❌ | |
| 14. proposal_deepening | ✅ | ❌ | |
| 15. export | ✅ | ❌ | |

**Honest note:** The B175 E2E integration test verifies all 16 stages execute with mocked providers. But mocked providers return controlled data and never timeout. Real execution hits different failure modes.

### Rate Limit Retry — Code Present, Not Live-Tested

The retry wrapper in `backend/providers/retry.py` exists and all 13 tests pass. But no live test triggered a 429 during this session. The retry logic will work if the exception has a `status_code` attribute or contains "429" in the string. It may not catch all provider-specific error formats.

### Stage Observability — Code Present, Not Persisted

The `StageReport` dataclass exists. The orchestrator appends entries. But the DB write doesn't happen. The feature is structurally complete but functionally invisible.

---

## Test Count: Honest Assessment

| Metric | Value |
|:-------|:------|
| Tests collected | 2,849 |
| B172-B177 tests | 106 new |
| Tests that would have caught the preflight bug | 0 |
| Tests that verify stage_report persists to DB | 0 |
| Tests that verify scores persist to idea rows | 0 |
| Tests that verify ingestion completes in reasonable time | 0 |

**The 2,849 tests are structural.** They verify that code exists, imports correctly, and returns expected types when mocked. They do NOT verify that the system actually works end-to-end with real services.

---

## Frontend — Not Live-Tested This Session

20 pages and 86 components exist on disk. Previous live E2E tests (v1-v6) verified they render in the browser. I did not restart the frontend this session. Key known issues from prior tests:
- Run detail page back button goes to `/pipeline/new` (not `/pipeline`)
- idea-detail.tsx has pre-existing TypeScript errors
- Onboarding overlay works but has not been tested by a real user

---

## Summary Scorecard

| Category | Works | Doesn't Work | Untested |
|:---------|:------|:-------------|:---------|
| Backend API endpoints | 10/10 tested | 0 | 72 not live-tested |
| Pipeline stages wired | 16/16 | 0 | — |
| Pipeline stages live-verified | 2/16 | 0 | 14/16 |
| Data persistence | Partial | stage_report, scores | — |
| Preflight | ✅ (after fix) | Was broken for all of B172-B177 | — |
| Watchdog | ✅ | — | — |
| Stale detection | ✅ | — | — |
| Rate limit retry | Code only | — | Not live-tested |
| Frontend | 20 pages exist | Not tested this session | — |
| Tests | 2,849 pass | Don't catch real bugs | — |

---

## The One Honest Sentence

The platform can start a pipeline run and find papers. Everything after that is code on disk that hasn't been live-verified in this session. The 2,849 tests prove the code exists, not that it works.
