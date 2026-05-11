# Batch Blueprint Sequence — Honest Remediation Roadmap

**Project:** Elephant Rock Research Platform
**Lead:** ivory-wolf (Craft Agent, §5.3 Lead Override)
**Framework:** AIV v5.3
**Date:** 2026-05-11
**Motivation:** User-identified dishonesty in prior batch reporting. 3 of 16 declared pipeline stages were dead code. Pipeline accepted runs without preflight validation. Tests verified structure, not function.

---

## Batch Sequence Overview

| Batch | Goal | Strategic Bet | Cycle | Tasks | Est. Tests |
|:------|:-----|:--------------|:------|:------|:-----------|
| **BATCH-172** | Wire Dead Stages + Preflight | 3 coded-but-unwired stages become functional; API stops lying about "running" status | STANDARD | 4 | +24 |
| **BATCH-173** | Stage Observability + Graceful Degradation | Users see exactly what ran, what skipped, and why; stages degrade instead of silently dying | STANDARD | 3 | +18 |
| **BATCH-174** | Functional Test Suite | Replace structural tests with tests that verify actual stage output quality | STANDARD | 3 | +20 |
| **BATCH-175** | End-to-End Pipeline Integration Test | One test that runs the full 16-stage pipeline with mock providers and verifies every stage executes | STANDARD | 2 | +8 |
| **BATCH-176** | Rate Limit Resilience | Pipeline survives 429 errors with exponential backoff and user-visible retry status | STANDARD | 2 | +10 |
| **BATCH-177** | Stale Run Cleanup + Run Status Accuracy | Fix stuck "running" runs; add heartbeat timeout; surface real completion state | STANDARD | 2 | +8 |

**Total:** 6 batches, 16 tasks, ~88 new functional tests

**Risk-first ordering:** BATCH-172 fixes the core dishonesty (dead stages + false "running"). BATCH-173 makes the pipeline's actual behavior visible. BATCH-174 replaces the vanity test count with real validation. BATCH-175-177 harden reliability.

---

# COMPLETE SPECIMEN: BATCH-172 BLUEPRINT

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-172
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-11
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Mixed (TASK-01 first; TASK-02, TASK-03 parallel after; TASK-04 last)

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Wire the 3 dead-coded pipeline stages (GapReflectionStage,
IdeaReflectionStage, EvaluationStage) into the orchestrator's
_build_stages() method and add a preflight check system that
validates provider reachability before the API accepts a pipeline
run. After this Batch, the API MUST NOT return {"status":"running"}
unless the orchestrator can actually initialize and the database
can persist a run record.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add GapReflectionStage, IdeaReflectionStage, EvaluationStage
    to the return list of PipelineOrchestrator._build_stages()
    at their correct positions in _STAGE_ORDER (indices 3, 5, 11)
  - Each wired stage MUST use the correct provider (thinking_provider
    for reflection/evaluation, generation provider is NOT acceptable)
  - The preflight module (backend/pipeline/preflight.py — already exists)
    MUST be called by trigger_run() BEFORE returning "running"
  - If any preflight check returns FATAL severity, the API MUST
    return HTTP 503 with a structured error body listing all failures
  - If all checks pass or are WARNING-only, the API returns 202 as before
    but the response body now includes a "preflight" key with the report
  - The preflight check MUST verify: LLM provider reachable,
    embedding provider reachable (non-fatal), database writable,
    strategy registered, domain non-empty, export dir writable

What the code MUST NOT do:
  - MUST NOT change the behavior of any currently-working stage
  - MUST NOT add new pipeline stages beyond the 3 that already exist
  - MUST NOT remove or reorder any existing stage in _build_stages()
  - MUST NOT make preflight checks blocking for WARNING severity
    (only FATAL blocks the run)
  - MUST NOT introduce new dependencies beyond what's already imported

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  python -m pytest backend/tests/ -x -q --tb=line -p no:asyncio 2>&1 | tail -5

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: The _build_stages() return list MUST contain exactly 16
         PipelineStage instances matching the names in _STAGE_ORDER.
         Count is verified by test: len(stages) == 16 and
         [s.name for s in stages] must equal _STAGE_ORDER.

  HB-02: The API endpoint POST /api/v1/pipeline/run MUST NOT return
         HTTP 202 with {"status":"running"} if any preflight check
         reports FATAL severity. It MUST return HTTP 503 instead.
         Verified by test: mock a FATAL provider check, assert 503.

  HB-03: No existing stage may change its position in the execution
         order. The first 3 stages must remain: literature_search,
         ingestion, gap_analysis. The last stage must remain: export.
         Verified by test asserting stage_names[0:3] and stage_names[-1].

  HB-04: The preflight check MUST complete in under 30 seconds total.
         Each individual provider check MUST have a timeout of 15s
         (LLM) or 10s (embedding) or 5s (database/dir). If a check
         times out, it is treated as WARNING, not FATAL.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Current verified state:

Module: backend.pipeline.orchestrator.PipelineOrchestrator
  _STAGE_ORDER: list[str] — 16 entries (verified)
  _build_stages() -> list[PipelineStage] — currently returns 13 stages
  __init__(provider, stage_callback, settings, strategy)
  self._provider: LLMProvider (cloud glm-5.1 via z.ai)
  self._thinking_provider: LLMProvider | None (local qwen3-4b via LM Studio)

Module: backend.pipeline.stages
  GapReflectionStage(provider, reflector, threshold=0.6)
    name -> "gap_reflection"
    __init__ params: provider (LLMProvider), reflector (ReflectionStage | None), threshold (float)
  IdeaReflectionStage(provider, reflector, threshold=0.6)
    name -> "idea_reflection"
    __init__ params: same as GapReflectionStage
  EvaluationStage(provider, evaluator)
    name -> "evaluation"
    __init__ params: provider (LLMProvider), evaluator (ProposalEvaluator | None)

Module: backend.pipeline.reflection.reflector
  ReflectionStage(provider, threshold=0.6, max_iterations=3)

Module: backend.pipeline.evaluation.proposal_evaluator
  ProposalEvaluator(provider)

Module: backend.pipeline.preflight (ALREADY EXISTS)
  run_preflight(domain, strategy, settings) -> PreflightReport
  PreflightReport.checks: list[PreflightResult]
  PreflightReport.can_proceed: bool (True if 0 FATAL)
  PreflightResult(name, severity, message, detail, latency_ms)
  CheckSeverity: OK | WARNING | ERROR | FATAL

Module: backend.api.routes.pipeline
  trigger_run(request: PipelineRunRequest) -> {"run_id", "status"}
  Currently returns 200 immediately without preflight.

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AUTH-01: Only the Lead Programmer may modify _STAGE_ORDER.
  AUTH-02: Preflight FATAL severity is the sole gate for rejecting
           a pipeline run. WARNING must not block.
  AUTH-03: The thinking_provider (local LM Studio) is preferred for
           reflection and evaluation stages. If unavailable, the
           generation provider (cloud) is an acceptable fallback —
           but a WARNING must be logged.
  AUTH-04: Strategy stage gating (existing behavior) remains unchanged.
           If a strategy disables a stage via StageConfig(enabled=False),
           that stage is skipped even after wiring. This is by design.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  - backend.pipeline.stages (GapReflectionStage, IdeaReflectionStage,
    EvaluationStage — exist, unmodified)
  - backend.pipeline.reflection.reflector.ReflectionStage (exists)
  - backend.pipeline.evaluation.proposal_evaluator.ProposalEvaluator (exists)
  - backend.pipeline.preflight (exists from prior session)
  - backend.api.routes.pipeline.trigger_run (exists, needs modification)
  - No external dependencies. No new packages.

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists:       [x] YES
  Last Updated:            2026-05-11 (BATCH-171)
  Batches since update:    0
  Reconciliation audit:    [x] N/A (< 5 batches since update)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  2,743 existing tests
  Expected delta (all Tasks):      +24 new tests
  Expected total at Batch close:   2,767

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-172/TASK-01 — Wire 3 Dead Stages into Orchestrator
  Priority:          Critical
  Description:       Add GapReflectionStage (position 3), IdeaReflectionStage
                     (position 5), and EvaluationStage (position 11) to the
                     return list of _build_stages() in orchestrator.py.
                     Each stage must receive the correct provider:
                     - Reflection stages use thinking_provider (fallback: self._provider)
                     - Evaluation uses thinking_provider (fallback: self._provider)
                     Create ReflectionStage and ProposalEvaluator instances
                     as needed.
  Files in scope:    backend/pipeline/orchestrator.py (lines ~990-1013, _build_stages method)
  Depends on:        None
  Required Tests:
    | Test ID            | Type       | Behavior Verified                          | Failure Mode                              | Falsified By                                         | Pass Criteria                                    |
    |:-------------------|:-----------|:-------------------------------------------|:------------------------------------------|:-----------------------------------------------------|:-------------------------------------------------|
    | TEST-172-01-01     | unit       | _build_stages returns exactly 16 stages    | Stage count mismatch silently breaks pipeline | Remove one stage from return list                    | assert len(stages) == 16                          |
    | TEST-172-01-02     | unit       | Stage names match _STAGE_ORDER exactly     | Wrong stage order causes data flow errors | Swap two stage positions in return list              | assert [s.name for s in stages] == _STAGE_ORDER  |
    | TEST-172-01-03     | unit       | gap_reflection stage is present at index 3 | Gap reflection never executes             | Comment out GapReflectionStage from return list      | assert stages[3].name == "gap_reflection"         |
    | TEST-172-01-04     | unit       | idea_reflection stage is present at index 5| Idea reflection never executes            | Comment out IdeaReflectionStage from return list     | assert stages[5].name == "idea_reflection"        |
    | TEST-172-01-05     | unit       | evaluation stage is present at index 11    | Multi-dim evaluation never executes       | Comment out EvaluationStage from return list         | assert stages[11].name == "evaluation"            |
    | TEST-172-01-06     | unit       | Reflection stages use thinking_provider    | Reflection uses cloud (wrong, expensive)  | Change provider assignment to self._provider only    | assert stage._provider is thinking_provider       |
    | TEST-172-01-07     | integration| Orchestrator initializes without error     | Missing constructor arg crashes startup   | Remove a required parameter from stage constructor   | PipelineOrchestrator() succeeds with no exception |
  Acceptance Criteria:
    AC-01-01: _build_stages() returns 16 stages with names matching _STAGE_ORDER
    AC-01-02: GapReflectionStage is at index 3, IdeaReflectionStage at index 5, EvaluationStage at index 11
    AC-01-03: Reflection and evaluation stages receive thinking_provider when available
    AC-01-04: Orchestrator.__init__() does not raise when constructing all 16 stages
  Traceability:
    AC-01-01 → TEST-172-01-01, TEST-172-01-02
    AC-01-02 → TEST-172-01-03, TEST-172-01-04, TEST-172-01-05
    AC-01-03 → TEST-172-01-06
    AC-01-04 → TEST-172-01-07

TASK-02: BATCH-172/TASK-02 — Wire Preflight into API Endpoint
  Priority:          Critical
  Description:       Modify trigger_run() in backend/api/routes/pipeline.py
                     to call run_preflight() BEFORE creating the background task.
                     If PreflightReport.can_proceed is False (any FATAL),
                     return HTTP 503 with structured error body.
                     If can_proceed is True, return 202 with "preflight" key
                     in the response body.
  Files in scope:    backend/api/routes/pipeline.py (trigger_run function, lines ~30-163)
  Depends on:        None (parallel with TASK-01)
  Required Tests:
    | Test ID            | Type       | Behavior Verified                          | Failure Mode                              | Falsified By                                         | Pass Criteria                                    |
    |:-------------------|:-----------|:-------------------------------------------|:------------------------------------------|:-----------------------------------------------------|:-------------------------------------------------|
    | TEST-172-02-01     | unit       | Preflight module is importable             | Import error blocks all runs              | Add syntax error to preflight.py                     | from backend.pipeline.preflight import run_preflight succeeds |
    | TEST-172-02-02     | integration| API returns 503 when LLM provider is FATAL | User sees "running" when pipeline can't start | Mock LLM check to return FATAL                      | response.status_code == 503                        |
    | TEST-172-02-03     | integration| API returns 503 when database is FATAL     | Run created with no DB                    | Mock DB check to raise exception                     | response.status_code == 503                        |
    | TEST-172-02-04     | integration| API returns 202 with preflight report on success | Preflight blocks healthy runs          | All checks pass, assert response status              | response.status_code == 202, "preflight" in response.json() |
    | TEST-172-02-05     | integration| API returns 202 when embedding is WARNING  | Embedding failure blocks run unnecessarily| Mock embedding to timeout (WARNING, not FATAL)       | response.status_code == 202                        |
    | TEST-172-02-06     | unit       | Preflight report structure is correct      | Missing fields in response                | Remove severity field from PreflightResult            | report has .checks, .can_proceed, .warnings, .errors, .fatal |
    | TEST-172-02-07     | integration| 503 response body lists all failures       | User can't diagnose what's wrong          | Mock 2 FATAL checks, assert both listed in body      | assert len(response.json()["preflight"]["fatal_checks"]) >= 2 |
  Acceptance Criteria:
    AC-02-01: POST /api/v1/pipeline/run returns 503 with structured error when any FATAL preflight check
    AC-02-02: POST /api/v1/pipeline/run returns 202 with preflight key when all checks pass or WARNING-only
    AC-02-03: Embedding provider failure results in WARNING (not FATAL) — run is still accepted
    AC-02-04: 503 response body contains enough detail for user to diagnose the problem
  Traceability:
    AC-02-01 → TEST-172-02-02, TEST-172-02-03
    AC-02-02 → TEST-172-02-04, TEST-172-02-05
    AC-02-03 → TEST-172-02-05
    AC-02-04 → TEST-172-02-07

TASK-03: BATCH-172/TASK-03 — Strategy Preset Validation
  Priority:          High
  Description:       Verify that all 4 strategy presets (fast_scan, deep_research,
                     academic_proposal, literature_review) correctly enable/disable
                     the 3 newly wired stages. Specifically:
                     - deep_research and academic_proposal MUST enable gap_reflection,
                       idea_reflection, and evaluation
                     - fast_scan and literature_review MUST disable them
                     Update presets.py if any stage is missing from the config.
  Files in scope:    backend/pipeline/strategies/presets.py
  Depends on:        None (parallel with TASK-01 and TASK-02)
  Required Tests:
    | Test ID            | Type       | Behavior Verified                          | Failure Mode                              | Falsified By                                         | Pass Criteria                                    |
    |:-------------------|:-----------|:-------------------------------------------|:------------------------------------------|:-----------------------------------------------------|:-------------------------------------------------|
    | TEST-172-03-01     | unit       | deep_research enables gap_reflection       | Reflection skipped on deep runs           | Set gap_reflection StageConfig(enabled=False)        | assert config.stages["gap_reflection"].enabled is True |
    | TEST-172-03-02     | unit       | deep_research enables idea_reflection      | Idea reflection skipped on deep runs      | Set idea_reflection StageConfig(enabled=False)       | assert config.stages["idea_reflection"].enabled is True |
    | TEST-172-03-03     | unit       | deep_research enables evaluation           | Evaluation skipped on deep runs           | Set evaluation StageConfig(enabled=False)            | assert config.stages["evaluation"].enabled is True |
    | TEST-172-03-04     | unit       | fast_scan disables all 3 new stages        | Fast scan runs expensive stages           | Set all 3 to enabled=True                            | assert all 3 are StageConfig(enabled=False) |
    | TEST-172-03-05     | unit       | literature_review disables all 3           | Lit review runs unnecessary stages        | Set all 3 to enabled=True                            | assert all 3 are StageConfig(enabled=False) |
  Acceptance Criteria:
    AC-03-01: deep_research strategy enables gap_reflection, idea_reflection, and evaluation
    AC-03-02: fast_scan strategy disables gap_reflection, idea_reflection, and evaluation
    AC-03-03: literature_review strategy disables gap_reflection, idea_reflection, and evaluation
    AC-03-04: academic_proposal strategy enables gap_reflection, idea_reflection, and evaluation
  Traceability:
    AC-03-01 → TEST-172-03-01, TEST-172-03-02, TEST-172-03-03
    AC-03-02 → TEST-172-03-04
    AC-03-03 → TEST-172-03-05

TASK-04: BATCH-172/TASK-04 — Verification and Batch Close
  Priority:          Medium
  Description:       Run the full test suite. Verify no regressions.
                     Verify _STAGE_ORDER matches _build_stages output names.
                     Verify preflight blocks FATAL and allows WARNING.
                     Create STATE.md update and CHANGELOG entry.
  Files in scope:    docs/aiv/STATE.md, CHANGELOG.md
  Depends on:        TASK-01, TASK-02, TASK-03
  Required Tests:
    | Test ID            | Type       | Behavior Verified                          | Failure Mode                              | Falsified By                                         | Pass Criteria                                    |
    |:-------------------|:-----------|:-------------------------------------------|:------------------------------------------|:-----------------------------------------------------|:-------------------------------------------------|
    | TEST-172-04-01     | integration| Full test suite passes with 0 failures     | New code broke existing tests             | Revert one wiring change, assert test failure        | pytest exit code 0, test count == 2,767 |
    | TEST-172-04-02     | integration| _STAGE_ORDER and _build_stages names match | Declared order differs from built order   | Add extra name to _STAGE_ORDER                       | assert [s.name for s in stages] == _STAGE_ORDER |
    | TEST-172-04-03     | integration| Preflight + trigger_run integration works  | Preflight not called or results ignored   | Remove preflight import, assert test failure         | 503 on FATAL, 202 on OK |
    | TEST-172-04-04     | unit       | STATE.md updated with BATCH-172 info       | State file stale                          | Check file content                                   | "BATCH-172" in STATE.md |
    | TEST-172-04-05     | unit       | CHANGELOG.md has BATCH-172 entry           | Missing audit trail                       | Check file content                                   | "BATCH-172" in CHANGELOG.md |
  Acceptance Criteria:
    AC-04-01: All 2,767 tests pass with 0 failures
    AC-04-02: _STAGE_ORDER matches _build_stages() output exactly
    AC-04-03: STATE.md and CHANGELOG.md updated
  Traceability:
    AC-04-01 → TEST-172-04-01
    AC-04-02 → TEST-172-04-02
    AC-04-03 → TEST-172-04-04, TEST-172-04-05

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: _build_stages() returns exactly 16 stages whose names
          match _STAGE_ORDER with zero deviations.
  BAC-02: POST /api/v1/pipeline/run returns HTTP 503 when any
          preflight check reports FATAL severity. Response body
          includes structured list of all failed checks.
  BAC-03: POST /api/v1/pipeline/run returns HTTP 202 with
          "preflight" key when all checks pass or are WARNING-only.
  BAC-04: All 4 strategy presets correctly enable/disable the
          3 newly wired stages.
  BAC-05: CHANGELOG.md updated with BATCH-172 entry.
  BAC-06: All documents archived under /docs/aiv/BATCH-172/.

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:
Review Cycle:             [1 or 2]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS — list each Reviewer flag acted on:
  FLAG-01 → Action taken:
  FLAG-02 → Action taken:

If REJECT — reason and next action:

Blueprint Version after response:
Lead Sign:                ivory-wolf — 2026-05-11

═══════════════════════════════════════════════════════════
```

---

## Batch Sequence Overview — BATCH-173 through BATCH-177

### BATCH-173: Stage Observability + Graceful Degradation
**Goal:** After every pipeline run, the run detail API returns a `stage_report` listing every stage in `_STAGE_ORDER` with its actual status: `executed`, `skipped_by_strategy`, `skipped_by_gate`, `skipped_by_error`, or `not_reached`. When a stage fails with an exception, the pipeline logs the error visibly and continues to the next stage instead of silently skipping. The frontend run-detail page shows this stage report.

**Strategic bet:** Making pipeline behavior fully visible will prevent the exact dishonesty pattern that occurred — "completed" hiding missing stages. Users and developers can see exactly what happened.

**Tasks:** 3 (stage report data model + API, error handling per-stage, frontend display)

---

### BATCH-174: Functional Test Suite
**Goal:** For each of the 16 pipeline stages, write at least one test that instantiates the stage, calls `execute()` with a minimal StageContext, and verifies the stage produces non-empty output (ideas, gaps, proposals, metrics, etc.) using a mock LLM provider that returns controlled responses. These tests replace structural tests as the quality gate.

**Strategic bet:** A test that verifies "GapReflectionStage.execute() returns a bool and modifies ctx.result" catches the dead-code problem. A test that verifies "module imports" does not.

**Tasks:** 3 (core stage functional tests, reflection/evaluation functional tests, export/output verification tests)

---

### BATCH-175: End-to-End Pipeline Integration Test
**Goal:** Write a single integration test that creates a PipelineOrchestrator with all providers mocked, runs `orchestrator.run(domain="test")`, and verifies all 16 stages execute in order, the result contains papers/gaps/ideas/proposals, and the stage_report shows 16/16 executed. This test runs on every commit.

**Strategic bet:** One integration test catches wiring failures that 100 unit tests miss. If any stage is dead-coded, this test fails.

**Tasks:** 2 (mock provider setup + full pipeline run, verification assertions)

---

### BATCH-176: Rate Limit Resilience
**Goal:** Implement exponential backoff (2s, 4s, 8s, max 3 retries) for the LLM provider on 429/503 responses. Surface retry status in stage_report. Add a configurable `rate_limit_retries` setting (default 3). When all retries exhausted, mark the stage as `skipped_by_error` in the stage report instead of crashing the pipeline.

**Strategic bet:** The 429 error that killed Run #109 is the most common production failure. Handling it gracefully turns a fatal error into a degraded-but-completed run.

**Tasks:** 2 (provider retry logic, stage-level error surfacing)

---

### BATCH-177: Stale Run Cleanup + Run Status Accuracy
**Goal:** Fix Run #110 (stuck as "running" forever). Add a watchdog that marks any run as "failed" if it's been "running" for more than 30 minutes. Add a `/api/v1/pipeline/runs/stale` endpoint that lists stuck runs. The run detail response now includes `stage_report` from BATCH-173 and `stale: bool` flag.

**Strategic bet:** A stuck "running" run is indistinguishable from a real running run. The watchdog ensures the database reflects reality within 30 minutes.

**Tasks:** 2 (watchdog timer + stale detection, run detail API enrichment)
