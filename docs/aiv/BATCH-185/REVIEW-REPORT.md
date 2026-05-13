# REVIEW REPORT

**Batch ID:** BATCH-185
**Blueprint Version:** 1.0 (implied — not explicitly stated)
**Cycle Mode:** STANDARD (4 Tasks)
**Reviewer:** Craft Agent (AI Reviewer Instance)
**Timestamp:** 2026-05-14T02:47:00+03:00
**Review Cycle:** 1
**Report ID:** REVIEW-BATCH-185-2026-05-14

---

## CHECKLIST RESULTS

### CHK-00 — CYCLE MODE: **PASS**
STANDARD cycle declared. 4 Tasks, modifies existing source files (`orchestrator.py`), multiple deliverables. Correct declaration.

### CHK-01 — BATCH ID: **PASS**
`BATCH-185` present and correctly formatted.

### CHK-02 — SLA FIELDS: **FLAG-02A**
No SLA fields present in the Blueprint. Review SLA, Execution SLA per Task, Partial Sign-Off SLA, and Review SLA are all missing. The AIV template requires these (defaults from §3.3 apply if not stated, but the fields must be present).

### CHK-03 — BATCH GOAL: **PASS**
"Port ML Intern's doom loop detection pattern to Elephant Rock's pipeline context" — single, clear, deployable outcome. Sufficiently specific.

### CHK-04 — SCOPE COMPLETENESS: **PASS**
MUST statements are embedded in the Solution section (detect identical consecutive outputs, detect repeating sequences, log warning, force stage to return). MUST NOT is implicit (no detection for stages other than gap/idea/proposal). However, the Blueprint does not use the formal MUST/MUST NOT section format.

### CHK-05 — BATCH ACCEPTANCE: **PASS**
Five acceptance criteria cover the full goal: doom_loop.py creation, orchestrator wiring, fingerprint scope limitation, 8 tests passing, zero regressions.

### CHK-06 — HARD BOUNDARIES: **FLAG-06A**
No Hard Boundaries section present. For a Standard Cycle Batch, HB declarations are mandatory. At minimum: HB-01 restricting doom detection to only the three declared stages, and HB-02 preventing the doom check from halting the pipeline (only skipping optional stages).

### CHK-07 — DATA MODELS: **FLAG-07A** / **FLAG-07B**
The Blueprint proposes a `StageOutputSignature` dataclass with `stage_name` and `output_hash` fields. This is a new model — not referencing existing codebase types, which is fine. However:

- **FLAG-07A:** The Blueprint says `_extract_stage_fingerprint` takes `PipelineResult` as a parameter. But the fingerprint extraction happens after each *individual stage* completes, not after the full pipeline. At that point, the `result` object is still being built — `result.gaps`, `result.ideas`, etc. are populated incrementally. The function signature should account for this, or the Blueprint should clarify that it reads from the partial `result` object.
- **FLAG-07B:** The fingerprint table says idea_generation uses "Concatenated idea titles + novelty scores". The actual `ResearchIdea` model has a `score` field (not `novelty_score`). The `IdeaCandidate` model has `overall_score`. The Blueprint should specify which score field to use.

### CHK-08 — AUTHORITY RULES: **FLAG-08A**
No Authority Rules section present. Who decides whether the doom loop detection is advisory (log only) or actionable (skip stages)? The Blueprint implies both: "log WARNING" and "force the stage to return." This authority should be explicit.

### CHK-09 — DEPENDENCY MAP: **FLAG-09A**
No formal Dependency Map section. The Blueprint references `huggingface/ml-intern` as a source but does not list prior Batch dependencies. STATE.md shows BATCH-173/176/177 as the most recent orchestrator-modifying Batches — these should be listed as dependencies since they modified stage execution and reporting.

### CHK-10 — TASK COMPLETENESS: **PASS (with notes)**
All 4 Tasks have descriptions, files in scope, and acceptance criteria. However:
- No formal Test ID table per AIV template format (Test IDs, Type, Behavior Verified, Failure Mode, Falsified By, Pass Criteria columns).
- The test list in TASK-04 is informal — it lists test names and descriptions but not in the required table format.

### CHK-11 — TASK COHERENCE: **PASS**
Each Task addresses one concern: TASK-01 (detection module), TASK-02 (orchestrator wiring), TASK-03 (fingerprint helper), TASK-04 (tests). TASK-03 is arguably part of TASK-01 or TASK-02 (it's a small helper), but it's not incoherent.

### CHK-12 — TEST COVERAGE: **FLAG-12A**
Tests are listed in TASK-04 but not in the required AIV v5.3 table format (Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria). The test descriptions are too informal for §13 compliance. Example: `test_01_identical_gaps_detected — 3 identical gap title lists → doom detected` lacks a Falsified By column entry.

### CHK-13 — TEST SUFFICIENCY: **FLAG-13A**
Missing test categories per T2:
- **Error path:** No test for what happens when `hash_stage_output` receives unhashable input (e.g., a result object with non-serializable fields).
- **Regression guard:** No test verifying that existing pipeline execution is unaffected when doom loop detection is disabled or history is empty.
- **Boundary condition:** `test_05_threshold_not_met` covers one boundary, but there is no test for the repeating-sequence boundary (what if the sequence repeats exactly once vs. 2+ times?).

### CHK-14 — TEST BASELINE: **FLAG-14A**
No Test Baseline section present. STATE.md reports 2,848 tests (verified in BATCH-177). The Blueprint should state this baseline and declare the expected delta (+8).

### CHK-15 — TASK DEPENDENCIES: **PASS**
Dependencies are logically consistent: TASK-02 depends on TASK-01 and TASK-03. TASK-04 depends on TASK-01. No circular dependencies. However, the Blueprint does not explicitly declare dependencies using the formal `Depends on:` field per Task block.

### CHK-16 — SCOPE COVERAGE: **FLAG-16A**
The Tasks collectively cover the solution, but there is a gap: no Task covers updating the monitoring module's exports or documentation. `backend/pipeline/monitoring/` has no `__init__.py` (confirmed — file does not exist). If `doom_loop.py` is added there, either an `__init__.py` must be created or the import path must be absolute. This is unscoped work.

### CHK-17 — INTERNAL CONSISTENCY: **FLAG-17A**
TASK-02 says "Add `self._doom_history: list[StageOutputSignature] = []` to `__init__`" but TASK-01 defines `StageOutputSignature` in `backend/pipeline/monitoring/doom_loop.py`. TASK-02 would need to import from monitoring, but this import is not listed. Additionally, TASK-02 references `_doom_history` as a list of `StageOutputSignature`, but `check_pipeline_doom` in TASK-01 takes `list[dict]` — these type signatures are inconsistent.

### CHK-18 — LINT COMMAND: **FLAG-18A**
No Lint Command field present. Required by AIV §3.1 template.

---

## INVESTIGATIVE LAYER

### CHK-19 — DATA MODEL VERIFICATION: **PASS**
Verified against actual codebase:
- `ResearchGap.title`: confirmed (gap_analysis/models.py:24)
- `ResearchIdea.title`: confirmed (generation/models.py:35)
- `ResearchIdea.score`: confirmed (generation/models.py:43) — Blueprint says "novelty scores" which maps to this field
- `IdeaCandidate.overall_score`: confirmed (generation/models.py:19)
- `ResearchProposal.sections`: confirmed (synthesis/proposal_synthesizer.py:76)
- `PipelineResult.stage_report`: confirmed (result.py) — list[StageReport]
- `StageReport`: confirmed with fields `name`, `status`, `elapsed_s`, `error`, `skip_reason`

### CHK-20 — FILE REALITY CHECK: **PASS**
- `backend/pipeline/orchestrator.py`: EXISTS. Stage loop confirmed at lines 1270–1430. The Blueprint's "around line 1185" is stale — the actual stage loop starts at ~1270 (pre-run setup occupies 1180–1270). This is an **Adaptation** waiting to happen.
- `backend/pipeline/monitoring/`: EXISTS as a directory with 3 files (`cost_tracker.py`, `health.py`, `pipeline_monitoring.py`). No `__init__.py` — this must be created.
- `backend/pipeline/monitoring/doom_loop.py`: DOES NOT EXIST — correctly declared as "to be created."
- `backend/tests/test_pipeline/test_batch185_doom_loop.py`: DOES NOT EXIST — correctly declared as "to be created."

### CHK-21 — SCOPE FEASIBILITY: **PASS**
All Tasks touch ≤3 files and expected LOC change is modest (<200 lines total). Well within the 60-minute Execution SLA default.

### CHK-22 — TASK BOUNDARY INTEGRITY: **FLAG-22A**
TASK-02 and TASK-03 share implicit coupling: TASK-02 calls `_extract_stage_fingerprint` (TASK-03) and then calls `check_pipeline_doom` (TASK-01). If TASK-03 changes the fingerprint extraction format, TASK-02's integration point silently breaks. The dependency should be declared explicitly: TASK-02 depends on TASK-01 AND TASK-03.

### CHK-23 — TEST PLAN ADEQUACY: **FLAG-23A** / **FLAG-23B** / **FLAG-23C**
- **FLAG-23A (T1 — Falsifiable):** No "Falsified By" column in the test list. Cannot verify falsifiability. Example: what code change would make `test_04_legitimate_variation_ok` fail? If doom detection is accidentally triggered by any non-empty history, this test should fail — but this isn't stated.
- **FLAG-23B (T2 — Error path):** No test for what happens when `hash_stage_output` receives `None`, a non-serializable object, or an empty `PipelineResult`. No test for `_extract_stage_fingerprint` when the stage result has unexpected structure.
- **FLAG-23C (T2 — Regression guard):** No test confirming that adding doom loop detection does not break existing pipeline runs or existing tests (2,848 baseline). The acceptance criterion says "zero regressions" but no dedicated regression test verifies this.

### CHK-24 — STATE CONSISTENCY: **FLAG-24A**
STATE.md exists and is current (Last Updated: 2026-05-13, BATCH-177). However:
- STATE.md Verified Module Map lists `backend.pipeline.orchestrator` verified in BATCH-172 with the note about `_STAGE_ORDER` having 16 entries and `_build_stages()`. The Blueprint does not reference STATE.md at all — no STATE.md STATUS section is present.
- STATE.md Test Baseline: 2,848. Blueprint does not reference this.

---

## TEST INTEGRITY PROTOCOL (§13) EVALUATION

### T1 — Falsifiability: **FLAG-T1**
No "Falsified By" descriptions for any of the 8 tests. Each test describes what it checks but not what concrete code change would make it fail. Required by §13.2.

### T2 — Category Coverage: **FLAG-T2**
- **Happy path:** Covered by tests 01, 02, 03, 04, 08.
- **Error path:** MISSING. No test for invalid/unexpected inputs to detection functions.
- **Boundary condition:** Partially covered by test 05 (threshold) and test 06/07 (empty/single). Missing: repeating-sequence boundary (exactly 1 repetition vs. 2).
- **Regression guard:** MISSING. No test verifying existing pipeline behavior is unchanged.

### T3 — Pass Criteria Specificity: **FLAG-T3**
Pass criteria are informal ("→ doom detected", "→ no doom"). The AIV template requires specific assertions, e.g., `assert result is not None` and `assert "doom" in result.lower()`.

### T4 — Orphan Assertions: **PASS**
No evidence of orphan assertions (too informal to evaluate deeply).

### T5 — Test-to-AC Traceability: **FLAG-T5**
No Traceability section present. The 5 acceptance criteria should map to the 8 tests. Notable gap: AC-03 ("Only gap/idea/proposal stages have fingerprints") has no explicit test — test_08 covers gap titles but not the exclusion of other stages.

### T6 — Mandatory Falsification: **N/A**
Task priorities are not declared in the Blueprint. If TASK-01 or TASK-04 are Critical/High, T6 falsification is mandatory. Without priority declarations, default is Medium — T6 is not mandatory but still recommended for the detection logic (safety-relevant code).

---

## SUMMARY

| Category | Count |
|:---|:---|
| Total Flags | 17 |
| Structural (CHK-01–18) | 9 |
| Investigative (CHK-19–24) | 3 |
| Test Integrity (T1–T6) | 5 |

**Severity:** **MEDIUM**

Most flags are structural omissions (missing AIV template fields: SLA, Hard Boundaries, Authority Rules, Dependency Map, Lint Command, Test Baseline, STATE.md STATUS). The investigative flags are substantive but not blocking — they reflect gaps between the Blueprint's informal format and the AIV v5.3 template requirements.

**Recommendation:** **PROCEED WITH CAUTION**

The underlying technical design is sound: doom loop detection is a well-scoped addition, the fingerprinting approach is reasonable, and the existing monitoring directory is the correct location. The main risk is that the Blueprint's informal format will produce Adaptations during execution (especially the orchestrator line-number reference and the type inconsistency between `StageOutputSignature` and `list[dict]`). The Lead should either:
1. Formalize the Blueprint to AIV v5.3 template format before execution, or
2. Accept the flags and instruct the Assistant to treat the informal format as a specification with the understanding that Adaptations will be more frequent.

---

## NOTES

1. **Line number reference is stale.** The Blueprint says "around line 1185" but the actual stage loop starts at ~1270. The Assistant should search for the stage iteration pattern (`for stage in self._stages:`) rather than relying on line numbers.

2. **Type inconsistency in `check_pipeline_doom`.** TASK-01 declares it takes `list[dict]` but the orchestrator stores `list[StageOutputSignature]`. The function should take `list[StageOutputSignature]` and handle conversion internally, or the orchestrator should pass raw dicts. This must be resolved before execution.

3. **Missing `__init__.py` in monitoring directory.** `backend/pipeline/monitoring/__init__.py` does not exist. Creating `doom_loop.py` there may require creating the init file or using absolute imports. This should be added to TASK-01's scope or declared as a known Adaptation.

4. **No `run()` method context shown.** The Blueprint says "Reset `_doom_history` at start of each `run()` call." The orchestrator's `run()` method is async and spans hundreds of lines. The Assistant will need to find the right insertion point. Consider adding a comment in TASK-02 like "Insert after `result = PipelineResult()` initialization."

5. **Fingerprint for `evaluation` stage is listed but should be excluded.** The fingerprint table lists `evaluation → Concatenated scores` but the Task description says "Only gap_analysis, idea_generation, and proposal_synthesis need fingerprints." This is contradictory. The evaluation row should be removed from the table, or the scope should be expanded.

6. **`_extract_stage_fingerprint` is private but used cross-module.** It's defined in TASK-03 as a private function (underscore prefix) but called from the orchestrator in TASK-02. Consider making it a public function in `doom_loop.py`, or clarify that TASK-03's function lives in the orchestrator module itself.
