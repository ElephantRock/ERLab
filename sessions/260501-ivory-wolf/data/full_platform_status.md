# Full Platform Status — Live Test Results

**Date:** 2026-05-11
**Method:** Live HTTP requests against running backend on port 8002
**Backend:** 97 registered endpoints, 20 frontend pages, 16 pipeline stages

---

## Backend API: 56 endpoints tested

### Working (41 endpoints)

| Endpoint | Status | Notes |
|:---------|:-------|:------|
| `GET /health` | 200 | Health check |
| `POST /auth/login` | 401 | Works — rejects bad credentials |
| `GET /auth/me` | 200 | Returns user info |
| `GET /pipeline/runs` | 200 | Lists all runs with pagination |
| `GET /pipeline/runs/detail/{id}` | 200 | Full run detail + stale flag |
| `GET /pipeline/runs/stale` | 200 | Lists stuck running runs |
| `POST /pipeline/watchdog` | 200 | Marks stale runs as failed |
| `GET /pipeline/runs/stats` | 200 | Run statistics |
| `GET /pipeline/runs/sessions` | 200 | Session listing |
| `GET /pipeline/plan` | 200 | Planning endpoint |
| `GET /pipeline/scheduler/status` | 200 | Scheduler status |
| `GET /pipeline/runs/{id}/ideas` | 200 | Ideas for a run |
| `GET /pipeline/runs/{id}/citation-graph` | 200 | Citation graph |
| `GET /pipeline/autonomous/history` | 200 | Autonomous run history |
| `GET /ideas/` | 200 | 131 ideas listed |
| `GET /ideas/{id}` | 200 | Single idea detail |
| `GET /ideas/{id}/comments` | 200 | Comment listing |
| `POST /ideas/{id}/feedback` | 200 | Feedback accepted |
| `POST /ideas/{id}/share` | 200 | Creates share token + URL |
| `GET /gaps/` | 200 | 252 gaps listed |
| `GET /gaps/stats` | 200 | Gap statistics |
| `GET /gaps/clusters` | 200 | Gap clustering |
| `GET /gaps/canonical` | 200 | Canonical gap list |
| `GET /gaps/export` | 200 | Gap export |
| `GET /gaps/{id}` | 200 | Single gap detail |
| `GET /gaps/{id}/papers` | 200 | Papers for a gap |
| `GET /gaps/{id}/related` | 200 | Related gaps |
| `POST /gaps/{id}/feedback` | 200 | Gap feedback accepted |
| `GET /knowledge-graph/stats` | 200 | 1,715 entities, 816 relationships |
| `GET /knowledge-graph/entities` | 200 | Entity listing |
| `GET /knowledge-graph/world-model` | 200 | World model |
| `GET /knowledge/stats` | 200 | Knowledge library stats |
| `GET /knowledge/documents` | 200 | Document listing |
| `GET /search/` | 200 | Search endpoint |
| `GET /search/knowledge/{domain}` | 200 | Domain knowledge query |
| `GET /notifications/` | 200 | Notification listing |
| `GET /status/` | 200 | System status |
| `GET /status/detailed` | 200 | Detailed status |
| `GET /status/evolution` | 200 | Evolution status |
| `GET /traces/summary` | 200 | Trace summary |
| `GET /traces/metrics` | 200 | Trace metrics |
| `GET /plugins/` | 200 | Plugin listing |
| `POST /plugins/install` | 200 | Plugin install |
| `GET /export/markdown/{id}` | 200 | 83KB markdown export |
| `GET /export/bibtex/{id}` | 200 | BibTeX export |

### Broken (9 endpoints)

| Endpoint | Status | Problem | Fix |
|:---------|:-------|:--------|:----|
| `GET /pipeline/runs/{id}/journal` | 404 | Journal file doesn't exist for old runs. Expected 404 — **not a bug**, just no journal for run #108 |
| `GET /literature/search` | 422 | Requires `?q=` query param — works with correct params | **Not a bug** — needs query param |
| `GET /memory/stats` | 503 | "Memory system is disabled" | Feature not enabled in config |
| `GET /memory/recall` | 422 | Requires query param — may also be disabled | Needs `?query=` + memory enabled |
| `GET /costs/summary` | 503 | "Cost tracking not available" | Cost tracker not initialized |
| `GET /costs/by-model` | 503 | Same | Same |
| `GET /costs/by-stage` | 503 | Same | Same |
| `GET /costs/by-provider` | 503 | Same | Same |
| `GET /governance/pending` | 503 | "Governance not initialized" | Feature not enabled in config |

### Error on execution (1 endpoint)

| Endpoint | Status | Problem |
|:---------|:-------|:--------|
| `POST /ideas/{id}/refine` | 500 | Internal server error — likely LLM call failure during idea refinement |

### Not applicable (correct rejection)

| Endpoint | Status | Why |
|:---------|:-------|:----|
| `PATCH /gaps/{id}/status` | 422 | Invalid status value "confirmed" — valid values: addressed, identified, investigating |
| `POST /sessions` | 404 | "Session management not enabled" |

### Not tested (39 endpoints)

Auth register, forgot-password, reset-password, pipeline/run (POST), pipeline/resume, pipeline/autonomous (POST), pipeline/sessions CRUD, pipeline/autonomous/stop, pipeline/scheduler/start/stop, knowledge/ingest, literature/ingest, notification stream/PATCH, idea comments POST, shared idea GET, experiments/run, recombination, export/pdf (POST), export/bulk, notification read-all.

---

## Pipeline: 2 of 16 stages verified live

| Stage | Verified | Result |
|:------|:---------|:-------|
| 0. literature_search | ✅ | ~74 seconds, finds papers |
| 1. ingestion | ⚠️ | Starts but takes 20+ min (sequential LLM calls) |
| 2. gap_analysis | ❌ | Never reached in live test |
| 3-15. all others | ❌ | Never reached in live test |

### Pipeline bugs found live

1. **Preflight had 2 bugs** — FIXED in `513057f`
2. **stage_report not persisted** — PipelineResult has the data, DB doesn't get it
3. **Idea scores are null** — 45 of 131 ideas have null novelty/feasibility scores
4. **Ingestion too slow** — 20+ minutes for ~30 papers

---

## Frontend: 20 pages (not tested this session)

Pages exist on disk. Previous E2E tests (v1-v6) confirmed they render. Not browser-tested tonight.

---

## Configuration gaps

| Feature | Config State | Impact |
|:--------|:-------------|:-------|
| Memory system | Disabled | /memory/* returns 503 |
| Cost tracking | Not initialized | /costs/* returns 503 |
| Governance | Not initialized | /governance/* returns 503 |
| Session management | Not enabled | /sessions/* returns 404 |
| S2 API key | Not set | Semantic Scholar excluded from search |
| Sentry DSN | Not set | No error monitoring |

---

## What "fully operational" requires

### Critical (platform doesn't work without these)
1. Fix stage_report persistence → 1 hour
2. Fix idea score persistence → 1 hour
3. Fix ingestion parallelization → 1 hour
4. Add LM Studio preflight check → 30 min
5. Write ONE real integration test → 1 hour

### High (major features non-functional)
6. Enable memory system in config → 15 min
7. Enable cost tracking initialization → 30 min
8. Enable governance initialization → 30 min
9. Fix idea refine endpoint (500 error) → 1 hour
10. Fix pipeline progress endpoint (hangs) → 1 hour

### Medium (nice to have)
11. Set S2_API_KEY → 5 min
12. Enable session management → 30 min
13. Frontend E2E browser test → 1 hour
14. Verify all 16 stages complete in real run → 30 min runtime

### Total: ~10-12 hours of work
