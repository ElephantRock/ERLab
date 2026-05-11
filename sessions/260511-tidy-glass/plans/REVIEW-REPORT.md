# REVIEW REPORT — BATCH-173

**Reviewer:** Craft Agent (AIV Framework v5.3 — Advisory Role)
**Date:** 2026-05-11
**Blueprint Version:** 1.0
**Mode:** STANDARD, 3 Tasks

---

## CHECKLIST RESULTS

### CHK-00 CYCLE MODE — PASS
STANDARD mode with 3 tasks modifying existing files (`result.py`, `orchestrator.py`, `pipeline.py`, `persistence.py`). Matches the STANDARD template.

### CHK-01 BATCH ID — PASS
BATCH-173 is present and correctly formatted as `BATCH-NN`.

### CHK-02 SLA FIELDS — PASS
Review SLA: 30 min (numeric). Execution SLA per Task: 60 min (numeric). Partial Sign-Off SLA: 15 min (numeric).

### CHK-03 BATCH GOAL — PASS
Single clear deployable outcome: per-stage execution status tracking with a `stage_report` array in the run detail API response.

### CHK-04 SCOPE — PASS
MUST section has 7 items (data model, tracking, exception handling, API exposure, persistence). MUST NOT section has 4 items (no stage logic changes, no pipeline halt, no removed error handling, no new migrations).

### CHK-05 BATCH ACCEPTANCE — PASS
BAC-01 through BAC-06 cover the full goal: report generation, non-halting behavior, API exposure, backward compatibility, changelog, and archiving.

### CHK-06 HARD BOUNDARIES — PASS
All 3 HBs are falsifiable:
- HB-01: Check `len(report) == 16` and all stages present.
- HB-02: Mock a stage to raise, assert subsequent stages execute.
- HB-03: Assert `stages_completed` is still populated.

### CHK-07 DATA MODELS — PASS
`StageReport` dataclass fields are specific with types. Module paths (`backend.pipeline.result`, `backend.pipeline.orchestrator`, `backend.api.routes.pipeline`, `backend.db.models.PipelineRun`) are real modules. `PipelineResult` class confirmed at the stated path.

### CHK-08 AUTHORITY RULES — PASS
3 authority rules present. No contradictions with HBs. AUTH-03 (literature_search halt) is consistent with the existing `return result` early-exit in `orchestrator.run()`.

### CHK-09 DEPENDENCY MAP — PASS
BATCH-172 dependency listed. Internal dependencies on existing modules are declared. No unresolved external deps.

### CHK-10 TASK COMPLETENESS — PASS
All 3 tasks have descriptions, files in scope, test IDs, and acceptance criteria.

### CHK-11 TASK COHERENCE — PASS
TASK-01: StageReport model + orchestrator tracking (one concern: reporting). TASK-02: Persistence + API exposure (one concern: externalization). TASK-03: Verification + batch close (one concern: validation). Clean separation.

### CHK-12 TEST COVERAGE — PASS
All 18 tests have IDs (TEST-173-XX-YY), types (unit/integration), behaviors, failure modes, falsification methods, and pass criteria.

### CHK-13 TEST SUFFICIENCY — FLAG
**FLAG:** No test explicitly covers the cascading multi-error scenario — i.e., when two stages both error out, both should appear as `skipped_by_error` and the pipeline should still complete with 16 entries. TEST-173-01-07 tests that subsequent stages execute after one error, and TEST-173-01-08 tests all 16 stages appear, but there is no test for consecutive `skipped_by_error` entries. This is a boundary condition gap.

### CHK-14 TEST BASELINE — PASS
Baseline: 2,769 tests (matches STATE.md BATCH-172 verified count). Expected delta: +18. Expected total: 2,787. Plausible and internally consistent.

### CHK-15 TASK DEPENDENCIES — PASS
TASK-01 → none. TASK-02 → TASK-01. TASK-03 → TASK-01, TASK-02. Sequential, non-circular, consistent with Task Sequencing: Sequential.

### CHK-16 SCOPE COVERAGE — PASS
MUST items map to tasks: data model + tracking → TASK-01, persistence + API → TASK-02. MUST NOT items are enforced by HB-02, HB-03 and AUTH-03.

### CHK-17 INTERNAL CONSISTENCY — FLAG
**FLAG:** The Blueprint claims TASK-01 covers "lines ~1160-1340" of `orchestrator.py`, but the actual stage execution loop (strategy skip at ~1210, gate skip at ~1230, execution at ~1255, checkpointing at ~1370) spans lines ~1195-1370. The line range is imprecise — the implementer may miss the strategy/gate/governance skip blocks which also need `StageReport` entries per the MUST list.

### CHK-18 LINT COMMAND — PASS
Present and non-empty: `python -m pytest backend/tests/test_pipeline/test_batch173_*.py -q --tb=line -p no:asyncio`. Follows the project convention (`-p no:asyncio` per GOTCHA-001).

---

## INVESTIGATIVE LAYER

### CHK-19 DATA MODEL VERIFICATION — PASS
- `backend.pipeline.result.PipelineResult` — confirmed, dataclass at `result.py` with 17 existing fields.
- `backend.pipeline.orchestrator.PipelineOrchestrator` — confirmed, class at `orchestrator.py`.
- `backend.api.routes.pipeline` — confirmed, module with `get_run` endpoint at `/runs/detail/{run_id}` returning `stages_completed` JSON.
- `backend.db.models.PipelineRun` — confirmed, SQLAlchemy model with `stages_completed` column (TEXT, default `"[]"`).
- `StageReport` is a new model — does not exist yet, which is expected.
- `_STAGE_ORDER` confirmed to have exactly 16 entries matching DEC-003/DEC-004 in STATE.md.

### CHK-20 FILE REALITY CHECK — PASS
All files in scope exist:
- `backend/pipeline/result.py` — exists, read confirmed.
- `backend/pipeline/orchestrator.py` — exists, read confirmed (~2050 lines).
- `backend/api/routes/pipeline.py` — exists, read confirmed.
- `backend/pipeline/persistence.py` — exists, read confirmed.

### CHK-21 SCOPE FEASIBILITY — FLAG
**FLAG:** TASK-01 is rated Critical priority with a 60-minute execution SLA. It requires: (1) creating a new dataclass, (2) adding a field to PipelineResult, (3) modifying the orchestrator `run()` loop with try/except around every stage execution point, (4) handling 5 status variants (executed, skipped_by_strategy, skipped_by_gate, skipped_by_error, not_reached), and (5) writing 8 unit/integration tests. The orchestrator `run()` method is ~280 lines of dense, heavily-branched code with strategy skips, gate skips, governance policy checks, cross-stage context, heartbeat monitoring, retry logic, and multiple persistence blocks. A 60-minute SLA for all of TASK-01 is optimistic — the implementer must modify 5+ distinct insertion points within the loop, each requiring careful placement to avoid breaking existing behavior.

### CHK-22 TASK BOUNDARY INTEGRITY — FLAG (FATAL)
**FLAG (FATAL):** The Blueprint asserts that "a stage exception must NOT terminate the pipeline" (HB-02, AUTH-03). However, the current `_execute_stage_with_retry` method **re-raises** the exception after exhausting retries (`raise` at line ~1800). The `try/finally` block in `run()` (line ~1272) only ensures the heartbeat is stopped — it does **not** catch the re-raised exception. This means any stage that fails after retries will propagate the exception upward and **terminate the entire pipeline run**.

The Blueprint's TASK-01 must introduce a `try/except` wrapper in the stage loop to catch these re-raised exceptions and convert them to `skipped_by_error` entries. This is not just undeclared shared state — it is a **fundamental behavioral change** that contradicts the current code's design (stages are expected to fail hard via re-raise). The Blueprint does not acknowledge this architectural tension or explain how to reconcile the retry mechanism with the non-halting requirement.

Additionally, the `run()` loop has multiple `continue` paths (strategy skip at ~1213, gate skip at ~1223, resume skip at ~1235, governance DENY at ~1250, governance GATE rejection at ~1262) that skip stages **without any tracking mechanism today**. The Blueprint assumes these are simple insertion points, but each `continue` must now also append a `StageReport` entry — and the governance `continue` blocks are inside nested `if` checks with audit event recording, making insertion non-trivial.

### CHK-23 TEST PLAN ADEQUACY — FLAG
**FLAG:**
- **T1 falsifiability:** TEST-173-01-01 through TEST-173-01-08 have clear pass criteria. TEST-173-01-08 asserts `len(report) == 16`, which directly falsifies HB-01. **Adequate.**
- **T2 error paths:** TEST-173-02-05 covers backward compatibility. However, there is no test for what happens when `stage_report` JSON exceeds the DB column size (no column exists yet — see CHK-24), or when `stage_report` serialization fails. **Partial gap.**
- **T6 for Critical:** There is no explicit T6-level smoke test or end-to-end test. TASK-01 is Critical but TEST-173-01-07 is the closest to an integration test (pipeline continues after error). TEST-173-01-08 runs a full pipeline and verifies all 16 stages, but it is typed as "unit" not "integration." **Misclassification.**

### CHK-24 STATE CONSISTENCY — FLAG
**FLAG:** STATE.md confirms the test baseline of 2,769 (verified in BATCH-172). STATE.md confirms `_STAGE_ORDER` has 16 entries and lists all 16 names (DEC-003, DEC-004). STATE.md does **not** mention a `stage_report` column on `PipelineRun` — because it doesn't exist yet. The Blueprint's DATA MODELS section states: "stage_report can be stored alongside in the same JSON or as a new approach via the result dict." This is ambiguous.

The DB model `PipelineRun` has `stages_completed` (TEXT, JSON array), `cluster_report_json` (TEXT, nullable), and `tree_data_json` (TEXT, nullable), but no `stage_report_json` column. The Blueprint's MUST NOT says "no new database migrations," so `stage_report` must be stored in an existing field. The only candidates are: (a) `stages_completed` — but co-storing a complex array of objects there would break backward compatibility since HB-03 requires `stages_completed` to remain populated as a simple name list, (b) `tree_data_json` or `cluster_report_json` — nullable fields that could be repurposed, but that would be semantically incorrect, (c) the `config_json` field — not appropriate for runtime data. The Blueprint needs to clarify the exact persistence strategy — e.g., serialize `stage_report` into a new JSON key within `stages_completed` (requiring a schema change to the stored format), or add a `stage_report_json` column via a migration (contradicting the MUST NOT). This ambiguity may cause TASK-02 to fail or violate HB-03.

---

## SUMMARY

| Check | Result |
|:------|:-------|
| CHK-00 | ✅ PASS |
| CHK-01 | ✅ PASS |
| CHK-02 | ✅ PASS |
| CHK-03 | ✅ PASS |
| CHK-04 | ✅ PASS |
| CHK-05 | ✅ PASS |
| CHK-06 | ✅ PASS |
| CHK-07 | ✅ PASS |
| CHK-08 | ✅ PASS |
| CHK-09 | ✅ PASS |
| CHK-10 | ✅ PASS |
| CHK-11 | ✅ PASS |
| CHK-12 | ✅ PASS |
| CHK-13 | ⚠️ FLAG — Missing test for cascading multi-error scenario |
| CHK-14 | ✅ PASS |
| CHK-15 | ✅ PASS |
| CHK-16 | ✅ PASS |
| CHK-17 | ⚠️ FLAG — Imprecise line range in TASK-01 files-in-scope |
| CHK-18 | ✅ PASS |
| CHK-19 | ✅ PASS |
| CHK-20 | ✅ PASS |
| CHK-21 | ⚠️ FLAG — 60-min SLA optimistic for TASK-01 scope |
| CHK-22 | 🚩 FLAG (FATAL) — Current code re-raises stage exceptions; Blueprint requires non-halting behavior without acknowledging the architectural conflict |
| CHK-23 | ⚠️ FLAG — Integration test misclassified as unit; no serialization error path test |
| CHK-24 | ⚠️ FLAG — Ambiguous persistence strategy for `stage_report` contradicts HB-03 (no new migrations) and no existing suitable column |

---

## FATAL FLAGS

1. **CHK-22:** `_execute_stage_with_retry` re-raises after exhausting retries (line ~1800). The `run()` loop has no catch wrapper around it — only a `try/finally` for heartbeat cleanup (line ~1272). HB-02 requires the pipeline to continue after stage errors, but the current architecture will crash the pipeline on any stage that fails 3+ times. The Blueprint must either: (a) declare that `_execute_stage_with_retry` will be modified to suppress re-raises (changing its contract), or (b) add a `try/except` around the entire stage execution block in `run()`. Either approach is a significant behavioral change that must be explicitly scoped, not assumed.

## ADVISORY FLAGS

1. **CHK-13:** Add a test for multiple consecutive stage errors to verify all appear as `skipped_by_error` and the pipeline still completes with 16 entries.
2. **CHK-17:** Update TASK-01 files-in-scope line range to "~1195-1370" to cover the strategy/gate/governance skip blocks.
3. **CHK-21:** Consider splitting TASK-01 into TASK-01a (data model + happy path) and TASK-01b (error handling + edge cases) to fit within SLA.
4. **CHK-23:** Reclassify TEST-173-01-08 as "integration" type. Add a test for `stage_report` serialization failure.
5. **CHK-24:** Clarify persistence: explicitly state which existing column will hold `stage_report` JSON, and demonstrate that co-storage with `stages_completed` won't violate HB-03.

---

## RECOMMENDATION

**HOLD — Revisions required before execution.**

The Blueprint is well-structured and internally consistent across CHK-00 through CHK-18 (17 of 18 surface-level checks pass). However, the Investigative Layer reveals a **fatal conflict** between HB-02 (non-halting behavior) and the actual codebase architecture (re-raises on retry exhaustion). The persistence strategy ambiguity (CHK-24) compounds this — without knowing where `stage_report` is stored, TASK-02 cannot be accurately estimated.

**Required before approval:**
1. Explicitly address the `_execute_stage_with_retry` re-raise behavior in TASK-01 scope or in a new MUST item.
2. Specify the exact persistence target column/field for `stage_report` and verify it does not conflict with HB-03.

**Advisory before approval:**
3. Add a multi-error-stage test case.
4. Correct the TASK-01 line range.
5. Reclassify TEST-173-01-08 as integration.
