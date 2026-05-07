# BATCH-115 BLUEPRINT — Evaluation Plan Generator

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-115
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-07
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Create an EvaluationPlanGenerator that produces concrete metrics,
baselines, and ablation designs for each proposal.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Create EvaluationPlanGenerator class with generate() method
  - Output: datasets, baselines, metrics with targets, ablation experiments
  - Template mode works without LLM provider

What the code MUST NOT do:
  - Must NOT require the LLM provider to be available
  - Must NOT modify the proposal synthesizer

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  python -m pytest --co -q 2>&1 | tail -1

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Generator failure must not halt the pipeline

───────────────────────────────────────────────────────────
DATA MODELS
───────────────────────────────────────────────────────────
  New file: backend/pipeline/evaluation/plan_generator.py
  Classes: EvaluationPlanGenerator, EvaluationPlan, DatasetRecommendation,
           BaselineMethod, MetricTarget, AblationExperiment

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists: [x] YES
  Last Updated: 2026-05-07
  Batches since update: 0

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline: 2,267 (after B114 close)
  Expected delta: +7
  Expected total: 2,274

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: Create EvaluationPlanGenerator
  Priority:          High
  Description:       Create backend/pipeline/evaluation/plan_generator.py with
                     EvaluationPlanGenerator class. Template mode generates structured
                     evaluation plan from proposal method text.
  Files in scope:
    - backend/pipeline/evaluation/plan_generator.py (NEW)
  Depends on:        None
  Required Tests:
    | Test ID         | Type | Behavior Verified              | Failure Mode          | Falsified By               | Pass Criteria              |
    |:----------------|:-----|:-------------------------------|:----------------------|:---------------------------|:---------------------------|
    | TEST-115-01-01  | unit | Generator class exists         | ImportError           | Remove file                | import succeeds            |
    | TEST-115-01-02  | unit | Template mode produces plan    | Empty output          | Return empty string        | len(plan.datasets) > 0     |
    | TEST-115-01-03  | unit | Plan includes datasets         | Missing datasets      | Skip dataset gen           | plan.datasets not empty    |
    | TEST-115-01-04  | unit | Plan includes baselines        | Missing baselines     | Skip baseline gen          | plan.baselines not empty   |
    | TEST-115-01-05  | unit | Plan includes metrics w/targets| No numeric targets    | Return None for targets    | any target > 0             |
    | TEST-115-01-06  | unit | Plan includes ablations        | Missing ablations     | Skip ablation              | len(ablations) >= 2        |
    | TEST-115-01-07  | unit | Handles empty input (HB-01)    | Crash on empty        | Pass empty string          | Returns default plan       |
  Acceptance Criteria:
    AC-01: EvaluationPlanGenerator produces structured plans
    AC-02: Template mode works without LLM
    AC-03: Empty input does not crash (HB-01)
  Traceability:
    AC-01 → TEST-115-01-02, TEST-115-01-03, TEST-115-01-04, TEST-115-01-05, TEST-115-01-06
    AC-02 → TEST-115-01-01, TEST-115-01-02
    AC-03 → TEST-115-01-07

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: EvaluationPlanGenerator produces structured plans
  BAC-02: All 7 tests pass
  BAC-03: CHANGELOG.md updated
  BAC-04: Documents archived under /docs/aiv/BATCH-115/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

Reviewer Report ID:       REVIEW-BATCH-115-2026-05-07
Review Cycle:             1
Lead Decision:            [x] ACCEPT

2 flags (CHK-14, CHK-24) — stale baseline from retroactive re-execution. Accepted.
Blueprint Version: 1.0
Lead Sign: ivory-wolf — 2026-05-07

═══════════════════════════════════════════════════════════
```
