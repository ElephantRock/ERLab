# BATCH BLUEPRINT — BATCH-173

Batch ID:                 BATCH-173
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-11
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential

---

## BATCH GOAL

Add per-stage execution status tracking so every pipeline run records which stages
executed, which were skipped (and why), and which failed (with error details).
When a stage throws an exception, the pipeline catches it, records the failure,
and continues to the next stage instead of silently skipping or crashing.
The run detail API response includes a `stage_report` array with this information.

---

## SCOPE STATEMENT

**What the code MUST do:**
- Create a `StageReport` data model with fields: `name`, `status` (executed/skipped_by_strategy/skipped_by_gate/skipped_by_error/not_reached), `elapsed_s`, `error` (optional string), `skip_reason` (optional string)
- After each stage execution attempt in `orchestrator.run()`, append a `StageReport` entry to a list on the `PipelineResult`
- When a stage raises an exception, catch it, record `status=skipped_by_error` with the error message, and continue to the next stage
- When a stage is skipped by strategy config, record `status=skipped_by_strategy` with the strategy name
- When a stage is skipped by a gate (novelty/feasibility/synthesis flags), record `status=skipped_by_gate` with the gate name
- The run detail API response (`GET /api/v1/pipeline/runs/detail/{id}`) must include `stage_report` in its response
- Persist `stage_report` in the pipeline_runs DB table (store as JSON in a new column or in existing `stages_completed`)

**What the code MUST NOT do:**
- MUST NOT change the execution logic of any stage
- MUST NOT stop the pipeline on a non-fatal stage error (only literature_search returning 0 papers should halt)
- MUST NOT remove existing error handling or webhook/notification logic
- MUST NOT add new database migrations (store in existing JSON-compatible fields)

---

## LINT COMMAND

```
python -m pytest backend/tests/test_pipeline/test_batch173_*.py -q --tb=line -p no:asyncio
```

---

## HARD BOUNDARIES

- **HB-01**: Every stage in `_STAGE_ORDER` must appear in the `stage_report`, even if it was never reached. Stages after a halt must have `status=not_reached`.
- **HB-02**: A stage exception must NOT terminate the pipeline. The pipeline must continue to the next stage. Verified by test: mock a stage to raise `RuntimeError`, assert subsequent stages still execute.
- **HB-03**: The existing `stages_completed` field in the DB must still be populated (backward compatibility). `stage_report` is additional, not a replacement.

---

## DATA MODELS / SCHEMA

**New model: `backend/pipeline/result.py`**
```python
@dataclass
class StageReport:
    name: str
    status: str  # "executed" | "skipped_by_strategy" | "skipped_by_gate" | "skipped_by_error" | "not_reached"
    elapsed_s: float = 0.0
    error: str | None = None
    skip_reason: str | None = None
```

**Existing model: `backend.pipeline.result.PipelineResult`**
- Add field: `stage_report: list[StageReport] = field(default_factory=list)`

**Existing module: `backend.pipeline.orchestrator.PipelineOrchestrator`**
- `run()` method: wrap each stage execution in try/except, append StageReport entries
- Skip blocks (strategy, gate) must also append StageReport entries

**Existing module: `backend.api.routes.pipeline`**
- Run detail endpoint must include `stage_report` in response

**Existing module: `backend.db.models.PipelineRun`**
- `stages_completed` column (TEXT, JSON array) — continues to be populated
- `stage_report` can be stored alongside in the same JSON or as a new approach via the result dict

---

## AUTHORITY RULES

- **AUTH-01**: Only the Lead may modify `StageReport.status` enum values
- **AUTH-02**: `skipped_by_error` must include the exception message (truncated to 500 chars) — no silent swallowing
- **AUTH-03**: The literature_search "no papers found" early exit remains the only pipeline-halting condition

---

## DEPENDENCY MAP

- BATCH-172 (wired stages, preflight) — MUST be closed before this batch
- `backend.pipeline.result.PipelineResult` — existing, will be modified
- `backend.pipeline.orchestrator.PipelineOrchestrator` — existing, will be modified
- `backend.api.routes.pipeline` — existing, will be modified

---

## STATE.md STATUS

- State file exists: YES
- Last Updated: 2026-05-11 (BATCH-172)
- Batches since update: 0
- Reconciliation audit: N/A

---

## TEST BASELINE

- Baseline at Blueprint issuance: **2,769** tests
- Expected delta (all Tasks): **+18** new tests
- Expected total at Batch close: **2,787**

---

## TASK LIST

### TASK-01: BATCH-173/TASK-01 — StageReport Data Model + Orchestrator Tracking
- **Priority:** Critical
- **Description:** Create `StageReport` dataclass. Add `stage_report` field to `PipelineResult`. Modify `orchestrator.run()` to append a `StageReport` entry for every stage: on execution, on strategy skip, on gate skip, on error, and on not-reached (stages after a halt).
- **Files in scope:** `backend/pipeline/result.py`, `backend/pipeline/orchestrator.py` (run method, lines ~1160-1340)
- **Depends on:** None

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-173-01-01 | unit | StageReport dataclass exists with correct fields | Missing model | Delete the class | Import succeeds, has name/status/elapsed_s/error/skip_reason |
| TEST-173-02-02 | unit | PipelineResult has stage_report field | Missing field | Remove field | `hasattr(result, 'stage_report')` and it's a list |
| TEST-173-01-03 | unit | Executed stage appears in report with status "executed" | No tracking | Remove append call | Report has entry with name and status="executed" |
| TEST-173-01-04 | unit | Strategy-skipped stage appears with "skipped_by_strategy" | Silent skip | Remove skip-report logic | Report has entry with status="skipped_by_strategy" |
| TEST-173-01-05 | unit | Gate-skipped stage appears with "skipped_by_gate" | Silent skip | Remove gate-report logic | Report has entry with status="skipped_by_gate" |
| TEST-173-01-06 | unit | Error stage appears with "skipped_by_error" and error message | Silent error swallow | Catch and re-raise | Report has entry with status="skipped_by_error" and non-empty error |
| TEST-173-01-07 | integration | Pipeline continues after stage error | Pipeline halts on error | Re-raise exception | Subsequent stages execute after error stage |
| TEST-173-01-08 | unit | All 16 stages appear in report (including not_reached) | Missing stages | Remove not-reached logic | `len(report) == 16` after pipeline run |

**Acceptance Criteria:**
- AC-01-01: StageReport dataclass with name, status, elapsed_s, error, skip_reason
- AC-01-02: PipelineResult.stage_report is a list populated during run()
- AC-01-03: All 16 stages appear in stage_report after any run
- AC-01-04: Stage errors don't halt the pipeline

**Traceability:** AC-01-01→T-01,T-02 | AC-01-02→T-02 | AC-01-03→T-03,T-04,T-05,T-08 | AC-01-04→T-06,T-07

---

### TASK-02: BATCH-173/TASK-02 — Persist + Expose Stage Report via API
- **Priority:** High
- **Description:** Store `stage_report` JSON in the DB (via the existing result dict or stages_completed). Add `stage_report` to the run detail API response.
- **Files in scope:** `backend/api/routes/pipeline.py` (run detail endpoint), `backend/db/crud.py` or `backend/pipeline/persistence.py`
- **Depends on:** TASK-01

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-173-02-01 | integration | Run detail API returns stage_report | Missing from response | Remove from response builder | `"stage_report" in response.json()` |
| TEST-173-02-02 | integration | stage_report has correct length (16 entries) | Truncated report | Return empty list | `len(response.json()["stage_report"]) == 16` |
| TEST-173-02-03 | integration | Executed stages have elapsed_s > 0 | No timing data | Set elapsed to 0 | At least one entry has `elapsed_s > 0` |
| TEST-173-02-04 | integration | Completed run has stages with "executed" status | All "not_reached" | Force early exit | At least 3 entries with status="executed" |
| TEST-173-02-05 | unit | Backward compat: stages_completed still populated | Field missing | Remove assignment | `stages_completed` field is still a non-empty list |

**Acceptance Criteria:**
- AC-02-01: Run detail API includes stage_report array
- AC-02-02: stage_report contains entries for all 16 stages
- AC-02-03: stages_completed field still populated (backward compat)

**Traceability:** AC-02-01→T-01,T-02 | AC-02-02→T-02 | AC-02-03→T-05

---

### TASK-03: BATCH-173/TASK-03 — Verification and Batch Close
- **Priority:** Medium
- **Description:** Run full test suite. Verify no regressions. Update STATE.md and CHANGELOG.
- **Files in scope:** `docs/aiv/STATE.md`, `CHANGELOG.md`
- **Depends on:** TASK-01, TASK-02

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-173-03-01 | integration | All batch173 tests pass | Test failure | Revert a change | 18/18 pass |
| TEST-173-03-02 | integration | All batch172 tests still pass | Regression | Revert wiring | 26/26 pass |
| TEST-173-03-03 | integration | Existing pipeline tests pass | Regression | Break orchestrator | Select existing tests pass |
| TEST-173-03-04 | unit | STATE.md has BATCH-173 | Stale state | Check content | `"BATCH-173" in STATE.md` |
| TEST-173-03-05 | unit | CHANGELOG has BATCH-173 | Missing trail | Check content | `"BATCH-173" in CHANGELOG.md` |

**Acceptance Criteria:**
- AC-03-01: All 18 new tests pass
- AC-03-02: All BATCH-172 tests still pass (no regression)
- AC-03-03: STATE.md and CHANGELOG updated

**Traceability:** AC-03-01→T-01 | AC-03-02→T-02 | AC-03-03→T-04,T-05

---

## BATCH-LEVEL ACCEPTANCE CRITERIA

- **BAC-01**: Every pipeline run produces a `stage_report` with entries for all 16 stages
- **BAC-02**: Stage exceptions do NOT halt the pipeline — subsequent stages execute
- **BAC-03**: Run detail API includes `stage_report` in response
- **BAC-04**: `stages_completed` field still populated (backward compatibility)
- **BAC-05**: CHANGELOG.md updated
- **BAC-06**: All documents archived under `/docs/aiv/BATCH-173/`

---

## LEAD RESPONSE TO REVIEW REPORT

[Leave blank until Review Report received.]
