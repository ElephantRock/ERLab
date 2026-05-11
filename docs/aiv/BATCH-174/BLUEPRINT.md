# BATCH BLUEPRINT — BATCH-174

Batch ID:                 BATCH-174
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-11
Review SLA:               30 min
Execution SLA per Task:   90 min
Partial Sign-Off SLA:     15 min
Task Sequencing: Sequential

---

## BATCH GOAL

Replace structural tests with functional tests that instantiate each pipeline stage,
call `execute()` with a minimal `StageContext`, and verify the stage produces meaningful
output using a mock LLM provider returning controlled responses. At least one functional
test per stage — 16 stages, 20+ new tests total.

---

## SCOPE STATEMENT

**What the code MUST do:**
- Write functional tests for all 16 pipeline stages that:
  1. Instantiate the stage with mocked dependencies
  2. Create a `StageContext` with a `PipelineResult` and sample data
  3. Call `stage.execute(ctx)` and assert it returns `True` (or `False` for early-exit stages)
  4. Verify the `PipelineResult` is mutated with non-empty output (gaps, ideas, proposals, metrics, etc.)
- Use a mock LLM provider that returns controlled, parseable JSON/text responses
- Each test must be independently runnable (no shared mutable state between tests)
- Tests must distinguish between "stage ran and produced output" vs "stage was mocked at import level"

**What the code MUST NOT do:**
- MUST NOT modify any stage implementation code
- MUST NOT modify the orchestrator
- MUST NOT add new fixtures or conftest changes that affect other test files
- MUST NOT use `@pytest.mark.asyncio` — use `asyncio.run()` directly

---

## LINT COMMAND

```
python -m pytest backend/tests/test_pipeline/test_batch174_*.py -v --tb=short -p no:asyncio
```

---

## HARD BOUNDARIES

- **HB-01**: Each of the 16 stages must have at least one test that calls `stage.execute(ctx)` — not just imports the module.
- **HB-02**: Tests must verify mutation of `PipelineResult` (or `ctx` state), not just that the function returned without error.
- **HB-03**: No changes to source code in `backend/pipeline/` — only test files are created.

---

## DATA MODELS / SCHEMA

**Test files (NEW):**
- `backend/tests/test_pipeline/test_batch174_core_stages.py` — TASK-01: stages 0-8 (9 stages)
- `backend/tests/test_pipeline/test_batch174_synthesis_stages.py` — TASK-02: stages 9-15 (7 stages)
- `backend/tests/test_pipeline/test_batch174_verification.py` — TASK-03: meta-verification

**Stage → Output mapping (what each test must verify):**

| # | Stage | Constructor Args | Must Mutate |
|:--|:------|:-----------------|:------------|
| 0 | LiteratureSearchStage | search_service, hooks | `ctx.all_papers` (via search results) |
| 1 | IngestionStage | embedding_service, summarizer | `ctx.result.papers_found` |
| 2 | GapAnalysisStage | provider, cluster_service, deduplicator | `ctx.result.gaps` |
| 3 | GapReflectionStage | provider | `ctx.result.gaps` modified (deepened) |
| 4 | IdeaGenerationStage | ideator | `ctx.result.ideas` |
| 5 | IdeaReflectionStage | provider | `ctx.result.ideas` modified (refined) |
| 6 | NoveltyCheckingStage | novelty_checker, s2_verifier | `ctx.result.novelty_reports` |
| 7 | FeasibilityScoringStage | provider | `ctx.result.feasibility_reports` |
| 8 | MechanicalMetricsStage | (none) | `ctx.result.mechanical_metrics` |
| 9 | ProposalSynthesisStage | provider | `ctx.result.proposals` |
| 10 | AdversarialReviewStage | provider | `ctx.result.critique_history` |
| 11 | EvaluationStage | provider | `ctx.result.evaluation_reports` |
| 12 | PaperSynthesisStage | provider | `ctx.result.proposals[idx].metadata` |
| 13 | CitationAuditStage | provider | `ctx.result.quality_report` or proposal metadata |
| 14 | ProposalDeepeningStage | provider | `ctx.result.proposals` modified |
| 15 | ExportStage | (config) | `ctx.result.export_paths` |

**Existing test infrastructure:**
- `backend/tests/test_pipeline/conftest.py` has existing fixtures — may be referenced but not modified
- Mock LLM pattern: Create a simple class with `complete()` returning a canned string, or use `MagicMock(spec_set=["complete"])`

---

## AUTHORITY RULES

- **AUTH-01**: Only the Lead may waive the "at least one test per stage" requirement
- **AUTH-02**: If a stage's constructor requires complex dependencies that can't be mocked, the test must document this as a known limitation and test what's possible (e.g., test the stage's `_process()` method directly)
- **AUTH-03**: Stages that return `False` (early exit like literature_search finding 0 papers) must have a test for BOTH True and False return paths

---

## DEPENDENCY MAP

- BATCH-172 (wired stages) — CLOSED
- BATCH-173 (stage_report) — CLOSED
- `backend/pipeline/stages.py` — READ ONLY
- `backend/pipeline/result.py` — READ ONLY

---

## STATE.md STATUS

- State file exists: YES
- Last Updated: 2026-05-11 (BATCH-173)
- Batches since update: 0
- Reconciliation audit: N/A

---

## TEST BASELINE

- Baseline at Blueprint issuance: **2,790** tests
- Expected delta (all Tasks): **+20** new tests
- Expected total at Batch close: **2,810**

---

## TASK LIST

### TASK-01: BATCH-174/TASK-01 — Core Stage Functional Tests (stages 0-8)
- **Priority:** Critical
- **Description:** Write functional tests for the first 9 pipeline stages (literature_search through mechanical_metrics). Each test instantiates the stage with mocked deps, creates a minimal StageContext, calls execute(), and verifies output mutation.
- **Files in scope:** NEW FILE `backend/tests/test_pipeline/test_batch174_core_stages.py`
- **Depends on:** None

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-174-01-01 | functional | LiteratureSearchStage.execute() populates ctx.all_papers | Stage not called | Remove execute call | `len(ctx.all_papers) > 0` |
| TEST-174-01-02 | functional | IngestionStage.execute() populates papers_found | No counting | Return early | `ctx.result.papers_found > 0` |
| TEST-174-01-03 | functional | GapAnalysisStage.execute() populates gaps | No gaps | Provider returns empty | `len(ctx.result.gaps) > 0` |
| TEST-174-01-04 | functional | GapReflectionStage.execute() modifies gaps | No modification | Skip stage | gaps have additional fields after reflection |
| TEST-174-01-05 | functional | IdeaGenerationStage.execute() populates ideas | No ideas | Ideator returns None | `len(ctx.result.ideas) > 0` |
| TEST-174-01-06 | functional | IdeaReflectionStage.execute() modifies ideas | No refinement | Skip stage | ideas have reflection metadata |
| TEST-174-01-07 | functional | NoveltyCheckingStage.execute() populates novelty_reports | No reports | Verifier returns empty | `len(ctx.result.novelty_reports) > 0` |
| TEST-174-01-08 | functional | FeasibilityScoringStage.execute() populates feasibility_reports | No scores | Provider returns empty | `len(ctx.result.feasibility_reports) > 0` |
| TEST-174-01-09 | functional | MechanicalMetricsStage.execute() populates metrics | No metrics | Return early | `len(ctx.result.mechanical_metrics) > 0` |

**Acceptance Criteria:**
- AC-01-01: 9 tests, one per stage, all calling execute()
- AC-01-02: Each test verifies PipelineResult mutation, not just return value
- AC-01-03: Mock LLM provider returns parseable responses

**Traceability:** AC-01-01→T-01..T-09 | AC-01-02→T-01..T-09 | AC-01-03→all

---

### TASK-02: BATCH-174/TASK-02 — Synthesis Stage Functional Tests (stages 9-15)
- **Priority:** Critical
- **Description:** Write functional tests for the remaining 7 pipeline stages (proposal_synthesis through export). Same pattern as TASK-01.
- **Files in scope:** NEW FILE `backend/tests/test_pipeline/test_batch174_synthesis_stages.py`
- **Depends on:** TASK-01 (uses same mock provider pattern)

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-174-02-01 | functional | ProposalSynthesisStage.execute() populates proposals | No proposals | Provider returns empty | `len(ctx.result.proposals) > 0` |
| TEST-174-02-02 | functional | AdversarialReviewStage.execute() populates critique_history | No critiques | Skip stage | `len(ctx.result.critique_history) > 0` |
| TEST-174-02-03 | functional | EvaluationStage.execute() populates evaluation_reports | No evaluation | Provider returns empty | `len(ctx.result.evaluation_reports) > 0` |
| TEST-174-02-04 | functional | PaperSynthesisStage.execute() modifies proposal metadata | No synthesis | Skip stage | proposals have paper content |
| TEST-174-02-05 | functional | CitationAuditStage.execute() populates quality_report or metadata | No audit | Skip stage | quality_report is not None or proposal metadata updated |
| TEST-174-02-06 | functional | ProposalDeepeningStage.execute() modifies proposals | No deepening | Return early | proposals have deepened content |
| TEST-174-02-07 | functional | ExportStage.execute() populates export_paths | No export | Skip stage | `len(ctx.result.export_paths) > 0` |

**Acceptance Criteria:**
- AC-02-01: 7 tests, one per stage, all calling execute()
- AC-02-02: Each test verifies PipelineResult mutation
- AC-02-03: Stages with proposal dependencies get pre-populated proposals in ctx

**Traceability:** AC-02-01→T-01..T-07 | AC-02-02→T-01..T-07 | AC-02-03→T-01,T-04,T-06

---

### TASK-03: BATCH-174/TASK-03 — Verification and Batch Close
- **Priority:** Medium
- **Description:** Run all batch174 tests. Verify no regressions. Update STATE.md and CHANGELOG.
- **Files in scope:** NEW FILE `backend/tests/test_pipeline/test_batch174_verification.py`, `docs/aiv/STATE.md`, `CHANGELOG.md`
- **Depends on:** TASK-01, TASK-02

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-174-03-01 | integration | All batch174 tests pass | Test failure | Revert a change | 16+/16+ pass |
| TEST-174-03-02 | integration | All batch172 + batch173 tests still pass | Regression | Break wiring | 47/47 pass |
| TEST-174-03-03 | unit | STATE.md has BATCH-174 | Stale state | Check content | `"BATCH-174" in content` |
| TEST-174-03-04 | unit | CHANGELOG has BATCH-174 | Missing trail | Check content | `"BATCH-174" in content` |

**Acceptance Criteria:**
- AC-03-01: All 20+ new tests pass
- AC-03-02: No regressions in batch172/batch173
- AC-03-03: STATE.md and CHANGELOG updated

**Traceability:** AC-03-01→T-01 | AC-03-02→T-02 | AC-03-03→T-03,T-04

---

## BATCH-LEVEL ACCEPTANCE CRITERIA

- **BAC-01**: At least 16 functional tests (one per stage) that call execute() and verify output mutation
- **BAC-02**: No source code changes in backend/pipeline/ — only test files
- **BAC-03**: All batch172 + batch173 tests still pass
- **BAC-04**: CHANGELOG.md updated
- **BAC-05**: All documents archived under `/docs/aiv/BATCH-174/`

---

## LEAD RESPONSE TO REVIEW REPORT

[Leave blank until Review Report received.]
