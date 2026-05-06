---
REVIEW REPORT
Batch ID:            BATCH-75
Blueprint Version:   1.0
Cycle Mode:          STANDARD
Reviewer:            AI Reviewer Instance
Timestamp:           2026-05-06T14:32:00Z
Review Cycle:        1
Report ID:           REVIEW-BATCH-75-2026-05-06

CHECKLIST RESULTS

  CHK-00  CYCLE MODE:           PASS — STANDARD cycle declared; 6 Tasks modify existing source files; batch has >1 Task. Consistent.

  CHK-01  BATCH ID:             PASS — BATCH-75 present and correctly formatted.

  CHK-02  SLA FIELDS:           PASS — Review SLA: 30 min; Execution SLA per Task: 60 min; Partial Sign-Off SLA: 15 min. All numeric.

  CHK-03  BATCH GOAL:           PASS — Single clear deployable outcome: fix defects from commit 81d5c3f, re-enable tree search, verify E2E completion.

  CHK-04  SCOPE COMPLETENESS:   PASS — Six MUST items and five MUST NOT items present.

  CHK-05  BATCH ACCEPTANCE:     PASS — BAC-01 through BAC-06 cover pipeline completion, type safety, changelog, archival, STATE.md creation, and test counts.

  CHK-06  HARD BOUNDARIES:      PASS — HB-01 through HB-05 are all falsifiable with specific runtime conditions (isinstance check, AttributeError guard, dedup query, JSON-serializability, retry count).

  CHK-07  DATA MODELS:          PASS — Field-level detail provided for IdeaCandidate, ResearchIdea, ResearchProposal, PipelineResult, and DB Idea model. Conversion map is explicit with safe defaults noted.

  CHK-08  AUTHORITY RULES:      PASS — Three authority rules present; none contradict a Hard Boundary.

  CHK-09  DEPENDENCY MAP:       PASS — Dependencies on prior commits and config are declared. Not verifiable from filesystem alone but that is expected.

  CHK-10  TASK COMPLETENESS:    PASS — All 6 Tasks have descriptions, files in scope, test IDs, and acceptance criteria.

  CHK-11  TASK COHERENCE:       FLAG — TASK-02 combines two distinct concerns (getattr hardening against IdeaCandidate objects AND dedup logic for duplicate rows) in a single Task.

  CHK-12  TEST COVERAGE:        PASS — Every test has an ID, type, and specific pass criteria with falsification instructions.

  CHK-13  TEST SUFFICIENCY:     PASS — Error-path tests present for TASK-01 (TEST-75-01-04), TASK-02 (TEST-75-02-01), TASK-04 (TEST-75-04-02, TEST-75-04-03). Boundary tests present for TASK-01 (TEST-75-01-02), TASK-02 (TEST-75-02-04), TASK-04 (TEST-75-04-04).

  CHK-14  TEST BASELINE:        FLAG — Baseline claims +22 new tests (1,869 → 1,891) but actual count across all Tasks is 19 (TASK-01: 5, TASK-02: 4, TASK-03: 3, TASK-04: 4, TASK-05: 3, TASK-06: 0 manual).

  CHK-15  TASK DEPENDENCIES:    PASS — TASK-05 depends on TASK-01/02/03/04; TASK-06 depends on TASK-01/02/03/05. No circular dependencies.

  CHK-16  SCOPE COVERAGE:       FLAG — TreeSearchStage._build_tree_data() accesses idea.id and idea.parent_idea_ids, which exist only on IdeaCandidate — no Task covers updating this method to work with ResearchIdea after the TASK-01 conversion.

  CHK-17  INTERNAL CONSISTENCY: FLAG — TASK-01 converts ideas to ResearchIdea, but _build_tree_data() (called in the same execute() method, lines ~824–840 of stages.py) will raise AttributeError on idea.id since ResearchIdea has no id field, creating a direct contradiction between the conversion goal and the untouched downstream code.

  CHK-18  LINT COMMAND:         PASS — Present and non-empty: `python -m pytest backend/tests/ --co -q 2>/dev/null | tail -1` (zero collection errors = clean).

  ── INVESTIGATIVE LAYER ──────────────────────────────────

  CHK-19  DATA MODEL VERIFICATION:   PASS — All module paths verified: backend/pipeline/generation/models.py (IdeaCandidate, ResearchIdea), backend/pipeline/synthesis/proposal_synthesizer.py (ResearchProposal as plain class with **sections), backend/pipeline/result.py (PipelineResult with ideas: list[ResearchIdea]), backend/db/models.py (Idea with title + pipeline_run_id). Field names and types match the Blueprint's schema section exactly.

  CHK-20  FILE REALITY CHECK:        PASS — All "Files in scope" exist and match described content: stages.py (TreeSearchStage class confirmed), persistence.py (persist_ideas method confirmed), proposal_synthesizer.py (raw review_result assignment confirmed in synthesize() method), arxiv_source.py (search method at ~lines 38–65, no retry logic present — defect confirmed). New test files (test_tree_search_types.py, test_persistence_hardening.py, test_arxiv_retry.py) do not yet exist — consistent with "new file" declarations.

  CHK-21  SCOPE FEASIBILITY:         PASS — No single Task touches >8 files or >500 LOC expected change. TASK-01 (~50 LOC in stages.py + new test file) and TASK-02 (~40 LOC in persistence.py + new test file) are the largest and are well within limits.

  CHK-22  TASK BOUNDARY INTEGRITY:   PASS — TASK-01 writes to PipelineResult.ideas (via ctx.result.ideas), TASK-02 reads from it (via result.ideas in persist_ideas). This is declared pipeline flow, not a silent coupling. No two Tasks modify the same struct without a declared dependency.

  CHK-23  TEST PLAN ADEQUACY:        FLAG — TASK-03 (TEST-75-03-01 through 03): no error-path test for the case where model_dump() fails or ensemble_reviewer returns an unexpected type, violating T2 for a High-priority Task.

  CHK-24  STATE CONSISTENCY:         PASS — STATE.md does not exist. Blueprint correctly acknowledges this as the first Batch under v5.3 with BAC-05 covering STATE.md creation at Batch Close. No stale module references or carry-forward obligations to contradict.

  ── END INVESTIGATIVE LAYER ──────────────────────────────

SUMMARY

  Total Flags:      5
  Severity:         HIGH
  Recommendation:   RECOMMEND REVISION

  Flag Detail:
    1. CHK-11  TASK-02 mixes getattr hardening and dedup logic in one Task.
    2. CHK-14  Test baseline arithmetic is wrong: 19 new tests declared across Tasks, not 22.
    3. CHK-16  _build_tree_data() accesses idea.id and idea.parent_idea_ids (IdeaCandidate-only fields) with no Task covering its update after conversion.
    4. CHK-17  The TASK-01 conversion to ResearchIdea will cause _build_tree_data() to crash on idea.id (AttributeError) in the same execute() method — the conversion goal contradicts the untouched downstream code.
    5. CHK-23  TASK-03 lacks an error-path test (T2) for model_dump() failure or unexpected ensemble_reviewer return type.

  Critical Path Note:
    Flags 3 and 4 are the highest-priority items. TreeSearchStage._build_tree_data() runs
    immediately after ctx.result.ideas assignment in execute(). After TASK-01 converts ideas
    to ResearchIdea, the call `idea.id` on line ~831 of stages.py will raise AttributeError
    because ResearchIdea has no `id` field. This will break the pipeline at the exact point
    the Batch is trying to fix. The Lead must either (a) add a Task to update _build_tree_data()
    to use ResearchIdea-compatible fields, or (b) extend TASK-01 scope to include this method.
---
