# BATCH-116 BLUEPRINT — PipelineEvaluator Integration + Gold Standards

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-116
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-07

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Wire PipelineEvaluator into the orchestrator so every run produces
a quality report. Create domain-specific gold-standard gap lists.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add _evaluate_pipeline() to orchestrator (runs after all stages)
  - Create gold_standards.py with gap lists for 3+ domains
  - Store evaluation report in PipelineResult.quality_report

What the code MUST NOT do:
  - Must NOT block pipeline if evaluation fails (HB-01)
  - Must NOT change gap or idea generation logic

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Evaluation failure must not halt the pipeline

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  python -m pytest --co -q 2>&1 | tail -1

───────────────────────────────────────────────────────────
DATA MODELS
───────────────────────────────────────────────────────────
  backend/pipeline/verification/gold_standards.py (NEW)
  backend/pipeline/orchestrator.py (MODIFY — add _evaluate_pipeline)
  backend/pipeline/result.py (MODIFY — add quality_report field)
  PipelineResult gets: quality_report: dict | None = None

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists: [x] YES
  Last Updated: 2026-05-07

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline: 2,274 (after B115 close)
  Expected delta: +7
  Expected total: 2,281

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: Wire PipelineEvaluator + Create Gold Standards
  Priority:          High
  Files in scope:
    - backend/pipeline/verification/gold_standards.py (NEW)
    - backend/pipeline/orchestrator.py (MODIFY)
    - backend/pipeline/result.py (MODIFY)
  Required Tests:
    | Test ID         | Type | Behavior Verified              | Failure Mode          | Falsified By               | Pass Criteria              |
    |:----------------|:-----|:-------------------------------|:----------------------|:---------------------------|:---------------------------|
    | TEST-116-01-01  | unit | Gold standards 3+ domains      | Missing domains       | Remove a domain            | len(GOLD_STANDARDS) >= 3   |
    | TEST-116-01-02  | unit | AI/NLP has 5+ gaps             | Insufficient gaps     | Remove gaps                | len(gold["AI/NLP"]) >= 5   |
    | TEST-116-01-03  | unit | _evaluate_pipeline exists      | Not wired             | Remove method              | hasattr confirmed          |
    | TEST-116-01-04  | unit | Quality score in [0,1]         | Score out of range    | Wrong calc                 | 0 <= score <= 1.0          |
    | TEST-116-01-05  | unit | Non-blocking on failure (HB-01)| Pipeline halts        | Raise exception            | Pipeline completes         |
    | TEST-116-01-06  | unit | Report stored in result        | Data lost             | Skip write                 | quality_report in result   |
    | TEST-116-01-07  | unit | Keyword overlap computes correctly | Wrong overlap     | Change calc                | overlap("a b c","b c d")~=0.67 |
  Acceptance Criteria:
    AC-01: PipelineEvaluator wired and produces quality reports
    AC-02: Gold standard gap lists exist for 3+ domains
    AC-03: Evaluation does not block pipeline (HB-01)
  Traceability:
    AC-01 → TEST-116-01-03, TEST-116-01-04, TEST-116-01-06
    AC-02 → TEST-116-01-01, TEST-116-01-02
    AC-03 → TEST-116-01-05

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: PipelineEvaluator wired with gold standards
  BAC-02: All 7 tests pass
  BAC-03: CHANGELOG.md updated
  BAC-04: Documents archived under /docs/aiv/BATCH-116/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Reviewer Report ID: REVIEW-BATCH-116-2026-05-07
Review Cycle: 1
Lead Decision: [x] ACCEPT
2 flags (stale baseline). Accepted.
Lead Sign: ivory-wolf — 2026-05-07

═══════════════════════════════════════════════════════════
```
