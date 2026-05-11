# BATCH BLUEPRINT — BATCH-177

Batch ID:                 BATCH-177
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-11
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing: Sequential

---

## BATCH GOAL

Add a `GET /api/v1/pipeline/runs/stale` endpoint that lists runs stuck in "running"
status beyond the timeout. Add a `stale: bool` flag to the run detail response
so the frontend can display a warning. Verify the existing watchdog correctly
marks stale runs as "failed".

---

## SCOPE STATEMENT

**What the code MUST do:**
- Add `GET /api/v1/pipeline/runs/stale` endpoint that queries for runs with `status="running"` and `created_at` older than the configurable timeout (default 30 min)
- Return a list of stale run summaries: `{"stale_runs": [{"id": 1, "run_id": "run_...", "domain": "...", "created_at": "...", "age_minutes": 45}], "count": N}`
- Add `"stale": true/false` field to the run detail response (`GET /runs/detail/{id}`)
- The `stale` flag is `true` when `status == "running"` AND `created_at` is older than the timeout
- The watchdog POST endpoint already exists — just verify it works with a test

**What the code MUST NOT do:**
- MUST NOT change the watchdog logic in `backend/pipeline/execution/watchdog.py`
- MUST NOT change the persistence methods `find_stale_runs` or `mark_stale_run_failed`
- MUST NOT auto-run the watchdog on every API call — stale detection is read-only query
- MUST NOT modify the frontend (that's a separate batch)

---

## LINT COMMAND

```
python -m pytest backend/tests/test_pipeline/test_batch177_*.py -v --tb=short -p no:asyncio
```

---

## HARD BOUNDARIES

- **HB-01**: The stale endpoint must NOT modify any runs — it's a read-only query
- **HB-02**: The `stale` flag in run detail must be `false` for completed/failed runs regardless of age
- **HB-03**: The existing watchdog endpoint `POST /watchdog` must still work unchanged

---

## DATA MODELS / SCHEMA

**Modified: `backend/api/routes/pipeline.py`**
- New endpoint: `GET /runs/stale` — queries `PipelineRun` with `status="running"` and age > timeout
- Modified endpoint: `GET /runs/detail/{id}` — add `"stale": bool` field

**Existing (READ ONLY):**
- `backend/pipeline/execution/watchdog.py` — `PipelineWatchdog` class
- `backend/pipeline/persistence.py` — `find_stale_runs()`, `mark_stale_run_failed()`
- `backend/db/models.py` — `PipelineRun` model with `status`, `created_at` fields

---

## AUTHORITY RULES

- **AUTH-01**: The stale timeout must be configurable via query parameter `timeout_minutes` (default 30, range 1-1440)
- **AUTH-02**: The `stale` flag computation uses the same timeout as the watchdog (30 min default)
- **AUTH-03**: Stale runs list is capped at 100 entries (prevent large result sets)

---

## DEPENDENCY MAP

- BATCH-173 (stage_report in run detail) — CLOSED
- `backend/pipeline/execution/watchdog.py` — READ ONLY
- `backend/pipeline/persistence.py` — READ ONLY
- `backend/api/routes/pipeline.py` — will be modified

---

## STATE.md STATUS

- State file exists: YES
- Last Updated: 2026-05-11 (BATCH-176)
- Batches since update: 0

---

## TEST BASELINE

- Baseline at Blueprint issuance: **2,839** tests
- Expected delta (all Tasks): **+8** new tests
- Expected total at Batch close: **2,847**

---

## TASK LIST

### TASK-01: BATCH-177/TASK-01 — Stale Runs Endpoint + Run Detail Stale Flag
- **Priority:** Critical
- **Description:** Add `GET /runs/stale` endpoint and `stale` flag to run detail. Both read-only queries against the DB.
- **Files in scope:** `backend/api/routes/pipeline.py`
- **Depends on:** None

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-177-01-01 | integration | GET /runs/stale returns 200 | 404/500 | Remove endpoint | `resp.status_code == 200` |
| TEST-177-01-02 | integration | GET /runs/stale returns stale_runs list | Missing key | Return empty dict | `"stale_runs" in resp.json()` |
| TEST-177-01-03 | integration | GET /runs/stale only returns running runs | Returns completed | Query all statuses | All returned runs have status="running" |
| TEST-177-01-04 | integration | GET /runs/stale respects timeout_minutes param | Ignores param | Always use default | Short-timeout returns more runs |
| TEST-177-01-05 | integration | Run detail has stale field | Missing field | Remove field | `"stale" in resp.json()` |
| TEST-177-01-06 | integration | Stale=false for completed runs | Always true | Check logic | Completed run returns `stale: false` |

**Acceptance Criteria:**
- AC-01-01: GET /runs/stale returns list of stale running runs
- AC-01-02: Run detail includes stale flag
- AC-01-03: Completed/failed runs always have stale=false

**Traceability:** AC-01-01→T-01..T-04 | AC-01-02→T-05 | AC-01-03→T-06

---

### TASK-02: BATCH-177/TASK-02 — Watchdog Verification + Batch Close
- **Priority:** High
- **Description:** Verify the existing watchdog endpoint works. Update STATE.md and CHANGELOG.
- **Files in scope:** NEW FILE `backend/tests/test_pipeline/test_batch177_stale.py`, `docs/aiv/STATE.md`, `CHANGELOG.md`
- **Depends on:** TASK-01

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-177-02-01 | integration | POST /watchdog marks stale runs as failed | No marking | Skip mark logic | Stale run gets status="failed" after watchdog |
| TEST-177-02-02 | integration | No regressions in batch172-176 | Regression | Revert wiring | Subprocess check passes |
| TEST-177-02-03 | unit | STATE.md has BATCH-177 | Stale | Check content | `"BATCH-177" in content` |
| TEST-177-02-04 | unit | CHANGELOG has BATCH-177 | Missing | Check content | `"BATCH-177" in content` |

**Acceptance Criteria:**
- AC-02-01: Watchdog correctly marks stale runs
- AC-02-02: No regressions
- AC-02-03: STATE.md and CHANGELOG updated

**Traceability:** AC-02-01→T-01 | AC-02-02→T-02 | AC-02-03→T-03,T-04

---

## BATCH-LEVEL ACCEPTANCE CRITERIA

- **BAC-01**: GET /runs/stale endpoint returns stale running runs
- **BAC-02**: Run detail includes `stale` flag (false for completed/failed)
- **BAC-03**: Watchdog still works (POST /watchdog)
- **BAC-04**: CHANGELOG.md updated
- **BAC-05**: All documents archived under `/docs/aiv/BATCH-177/`

---

## LEAD RESPONSE TO REVIEW REPORT

[Leave blank until Review Report received.]
