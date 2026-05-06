---
REVIEW REPORT
Batch ID:            BATCH-76
Blueprint Version:   1.0
Cycle Mode:          STANDARD
Reviewer:            AI Reviewer Instance
Timestamp:           2026-05-06T15:10:00Z
Review Cycle:        1
Report ID:           REVIEW-BATCH-76-2026-05-06

CHECKLIST RESULTS

  CHK-00  CYCLE MODE:           PASS — STANDARD cycle declared; 3 Tasks (2 Critical, 1 High); batch modifies existing source files and adds new modules. Consistent.

  CHK-01  BATCH ID:             PASS — BATCH-76 present and correctly formatted.

  CHK-02  SLA FIELDS:           PASS — Review SLA: 30 min; Execution SLA per Task: 60 min; Partial Sign-Off SLA: 15 min. All numeric and present.

  CHK-03  BATCH GOAL:           PASS — Single clear deployable outcome: pluggable strategy architecture allowing the pipeline to run in different modes via stage selection and parameterization.

  CHK-04  SCOPE COMPLETENESS:   PASS — Four MUST items and three MUST NOT items present. Both sets are specific and bounded.

  CHK-05  BATCH ACCEPTANCE:     PASS — BAC-01 through BAC-04 cover strategy selectability, behavioral parity with deep_research, changelog update, and document archival.

  CHK-06  HARD BOUNDARIES:      PASS — HB-01 (identical deep_research output) is falsifiable via output comparison. HB-02 (backward compat / default) is falsifiable by omitting strategy param. HB-03 (no DB migration) is falsifiable by checking for migration files.

  CHK-07  DATA MODELS:          PASS — Field-level detail provided for PipelineStrategy enum, StageConfig dataclass, StrategyConfig dataclass, and StrategyRegistry class. Methods and signatures are explicit.

  CHK-08  AUTHORITY RULES:      PASS — Four authority rules present (user-controlled selection, no-action default, immutability during run, Lead-only additions). None contradict a Hard Boundary.

  CHK-09  DEPENDENCY MAP:       PASS — Depends on BATCH-75 (current pipeline architecture). Required by 5 downstream batches. Declared and consistent with STATE.md.

  CHK-10  TASK COMPLETENESS:    PASS — All 3 Tasks have descriptions, files in scope, test IDs, acceptance criteria, and traceability matrices.

  CHK-11  TASK COHERENCE:       PASS — TASK-01 (models + registry), TASK-02 (orchestrator integration), TASK-03 (API + frontend) each address a single coherent concern with clear separation.

  CHK-12  TEST COVERAGE:        PASS — Every test has an ID, type, behavior verified, failure mode, falsification instructions, and specific pass criteria. 20 tests across 3 Tasks.

  CHK-13  TEST SUFFICIENCY:     PASS — Error-path tests present: TEST-76-01-08 (ValueError for invalid strategy), TEST-76-02-06 (ValueError before pipeline starts), TEST-76-03-04 (HTTP 400 for invalid strategy), TEST-76-03-05 (ValidationError). Boundary tests present: TEST-76-01-03 (default values), TEST-76-02-05 (strategy=None).

  CHK-14  TEST BASELINE:        FLAG — Baseline claims +45 new tests (1,901 → 1,946) but actual count across all Tasks is 20 (TASK-01: 8, TASK-02: 7, TASK-03: 5). Arithmetic does not match: 1,901 + 20 = 1,921, not 1,946.

  CHK-15  TASK DEPENDENCIES:    PASS — TASK-02 depends on TASK-01; TASK-03 depends on TASK-02. Sequential, no circular dependencies. Matches SEQUENTIAL task sequencing mode.

  CHK-16  SCOPE COVERAGE:       PASS — All files listed in DATA MODELS section map to specific Tasks. Orchestrator modification covered by TASK-02. API routes and schemas covered by TASK-03. No orphan references.

  CHK-17  INTERNAL CONSISTENCY: FLAG — TASK-01 TEST-76-01-07 asserts fast_scan disables "tree_search" and "knowledge" stages, but no such stage names exist in the orchestrator. The actual stage names from _STAGE_ORDER are: literature_search, ingestion, gap_analysis, idea_generation, novelty_checking, feasibility_scoring, mechanical_metrics, proposal_synthesis, export. There is no "tree_search" or "knowledge" stage — the closest are "idea_generation" (which may use TreeSearchStage) and "ingestion" / "novelty_checking" (knowledge-related). The test will fail unless the StrategyConfig stage keys are defined as arbitrary labels, but the orchestrator skip logic must then map these to actual PipelineStage instances — this mapping is unspecified.

  CHK-18  LINT COMMAND:         PASS — Present and non-empty: `python -m ruff check backend/ && python -m pytest --co -q`.

  ── INVESTIGATIVE LAYER ──────────────────────────────────

  CHK-19  DATA MODEL VERIFICATION:   PASS — Verified against source. PipelineOrchestrator.__init__() (orchestrator.py line ~120) accepts only provider, stage_callback, and settings — no strategy parameter exists yet, consistent with TASK-02 being a modification task. PipelineRunRequest (schemas.py) has no strategy field, consistent with TASK-03. PipelineRun DB model (models.py line ~104) uses config_json Text column, which can store strategy as JSON without migration — consistent with HB-03. _STAGE_ORDER in orchestrator.py lists 9 stages: literature_search, ingestion, gap_analysis, idea_generation, novelty_checking, feasibility_scoring, mechanical_metrics, proposal_synthesis, export. All model references in Blueprint are consistent with actual codebase.

  CHK-20  FILE REALITY CHECK:        PASS — Files to be modified confirmed to exist: backend/pipeline/orchestrator.py (PipelineOrchestrator class, __init__, run, _build_stages all verified), backend/api/routes/pipeline.py (trigger_run, list_runs verified), backend/api/schemas.py (PipelineRunRequest class verified), backend/config.py (Settings class verified). New files (backend/pipeline/strategies/__init__.py, models.py, registry.py, presets.py) do not yet exist — consistent with "NEW" declarations. Note: frontend/src/pages/pipeline-new.tsx not found on filesystem; if this is a monorepo with separate frontend build, this is expected, but TASK-03 lists it as MODIFIED.

  CHK-21  SCOPE FEASIBILITY:         PASS — TASK-01 creates 4 new files (~200 LOC estimated). TASK-02 modifies orchestrator.py (adding ~40 LOC for strategy acceptance and stage skipping). TASK-03 modifies 2 backend files (~30 LOC) and 3 frontend files (~60 LOC). No single Task exceeds 8 files or 500 LOC. Well within limits.

  CHK-22  TASK BOUNDARY INTEGRITY:   PASS — TASK-01 writes new module files (strategies/). TASK-02 reads from strategies/ and modifies orchestrator.py (declared dependency on TASK-01). TASK-03 reads from strategies/ and modifies API layer (declared dependency on TASK-02). No two Tasks modify the same file. Clean write boundaries.

  CHK-23  TEST PLAN ADEQUACY:        FLAG — TASK-02 has no integration test verifying that deep_research strategy actually produces identical output to the current pipeline (HB-01). TEST-76-02-02 checks stage execution list length but does not verify output equality. Given HB-01 is a Hard Boundary, a comparative integration test (run pipeline without strategy vs. with strategy="deep_research", assert result equality) should be present. Also, TASK-03 TEST-76-03-05 tests Pydantic ValidationError but no test verifies the actual HTTP 400 response path through FastAPI — only TEST-76-03-04 tests the endpoint, which covers this, but they are decoupled from the same validation chain.

  CHK-24  STATE CONSISTENCY:         PASS — STATE.md exists, last updated 2026-05-06 via BATCH-75. Blueprint correctly states "0 batches since update" and reconciliation audit is N/A (< 5 batches). STATE.md test baseline (1,901) matches Blueprint baseline (1,901). No carry-forward obligations. GOTCHA-001 through GOTCHA-004 are noted but none block strategy architecture work.

  ── END INVESTIGATIVE LAYER ──────────────────────────────

SUMMARY

  Total Flags:      4
  Severity:         HIGH
  Recommendation:   RECOMMEND REVISION

  Flag Detail:
    1. CHK-14  Test baseline arithmetic is wrong: 20 new tests declared across Tasks, not 45. Expected total should be 1,921, not 1,946.
    2. CHK-17  fast_scan strategy references disabling "tree_search" and "knowledge" stages, but no such stage names exist in _STAGE_ORDER. The actual stage names must be used (e.g., "idea_generation" for tree_search, and appropriate names for knowledge-related stages), or the strategy-to-stage mapping must be explicitly specified in the data model.
    3. CHK-23  No integration test verifying HB-01 (identical deep_research output). TEST-76-02-02 checks stage execution list length but does not assert output equality against the current pipeline behavior.
    4. CHK-20  (minor) frontend/src/pages/pipeline-new.tsx not found on filesystem. If frontend is a separate deployment unit, note this in the Blueprint; otherwise TASK-03 scope is not grounded.

  Critical Path Note:
    Flag 2 is the highest-priority item. The Blueprint's data model section specifies that
    fast_scan.stages maps stage names to StageConfig objects, and TEST-76-01-07 asserts
    `fast_scan.stages["tree_search"].enabled is False`. However, PipelineOrchestrator._STAGE_ORDER
    contains "idea_generation" (not "tree_search") and no stage named "knowledge" or "tree_search"
    exists. When TASK-02 implements the skip logic, it must resolve strategy stage keys to actual
    PipelineStage instances. The Lead must either (a) use actual _STAGE_ORDER names in the
    strategy presets (e.g., disable "idea_generation" for fast_scan if that is the intent, or
    "novelty_checking" for the knowledge-related stage), or (b) define an explicit mapping layer
    between strategy stage keys and PipelineStage.name values. Without this, the integration will
    fail at the orchestrator skip-logic step.
