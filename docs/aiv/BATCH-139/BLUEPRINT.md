BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-139
Blueprint Version:        1.1
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-10
Review SLA:               30 min
Execution SLA per Task:   90 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential (T2 depends on T1)

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Externalize all hardcoded compaction token budgets, paper limits,
abstract char limits, and constraint config values into config.py
so that pipeline quality-vs-cost tuning is possible via .env edits
without any code changes.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add config.py fields for stage token budgets (5 stages × 3 values:
    base, min, max) — stored as JSON string or individual fields
  - Add config.py fields for default paper limits per stage (5 values)
  - Add config.py fields for abstract char limits (tight/loose modes)
  - Add config.py fields for constraint config (max_size, max_growth_pct,
    min_sections, allow_empty)
  - Replace hardcoded DEFAULT_BUDGETS and DEFAULT_PAPER_LIMITS in
    budget_manager.py with settings reads
  - Replace hardcoded ConstraintConfig values in orchestrator.py with
    settings reads

What the code MUST NOT do:
  - Change any pipeline logic or control flow
  - Modify the QualityGate thresholds (already in config.py lines 147-153)
  - Modify MODEL_CONTEXT_SIZES or MODEL_PRICING reference tables
  - Change runtime behavior when .env uses current defaults
  - Remove existing config.py fields

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  python -m ruff check backend/ && npx tsc --noEmit --project frontend/tsconfig.json

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: All new config fields MUST have sensible defaults that
         match the current hardcoded values exactly. Verified by:
         Settings(_env_file=None) produces identical budget dicts
         to the current hardcoded DEFAULT_BUDGETS.

  HB-02: Existing tests MUST pass with zero regressions. New tests
         are additive only.

  HB-03: The application MUST start and /health MUST return 200.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
No data model changes. Existing modules referenced:

  Module:   backend.pipeline.compaction.budget_manager
  Class:    StageTokenBudget(base: int, min_budget: int, max_budget: int)
  Constants:
    DEFAULT_BUDGETS: dict = {
      "gap_analysis": StageTokenBudget(base=6000, min_budget=3000, max_budget=10000),
      "idea_generation": StageTokenBudget(base=8000, min_budget=4000, max_budget=15000),
      "novelty_checking": StageTokenBudget(base=4000, min_budget=2000, max_budget=8000),
      "feasibility_scoring": StageTokenBudget(base=2000, min_budget=1000, max_budget=4000),
      "proposal_synthesis": StageTokenBudget(base=10000, min_budget=5000, max_budget=20000),
    }
    DEFAULT_PAPER_LIMITS: dict = {
      "gap_analysis": 30, "idea_generation": 20,
      "novelty_checking": 10, "feasibility_scoring": 0,
      "proposal_synthesis": 15,
    }
    Abstract chars: 80 (tight mode), 150 (loose mode)
  Source:   backend/pipeline/compaction/budget_manager.py (verified)

  Module:   backend.pipeline.orchestrator
  Line 458: constraint_config = ConstraintConfig(max_size=5000, max_growth_pct=0.3, allow_empty=False, min_sections=3)
  Source:   backend/pipeline/orchestrator.py (verified)

  Module:   backend.config.Settings
  Existing compaction fields (lines 235-239):
    compaction_enabled: bool = True
    compaction_smart_truncation: bool = True
    compaction_summarization: bool = True
    compaction_budget_management: bool = True
    compaction_fallback_model: str = "gpt-4o"
  Source:   backend/config.py (verified 2026-05-10)

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AUTH-01: config.py is the SOLE source for budget/threshold defaults.
           budget_manager.py reads from settings; never hardcodes.

  AUTH-02: New config fields use a JSON-string approach for the budget
           dict (one field with a JSON value) rather than 15 individual
           fields. This keeps config.py manageable.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  Depends on: BATCH-138 (settings pattern established)

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists:       [x] YES
  Last Updated:            2026-05-10 (BATCH-138 Close)
  Batches since update:    0
  Reconciliation audit:    [x] N/A (< 5 batches)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  2,457 collected tests
  Expected delta (all Tasks):      +9 new tests (4 from T1 + 5 from T1 error-path + 3 from T2)
  Expected total at Batch close:   2,466

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-139/TASK-01 — Externalize compaction budgets and paper limits
  Priority:          High
  Description:      Add config.py fields for stage token budgets, paper limits,
                    and abstract char limits. Replace hardcoded DEFAULT_BUDGETS
                    and DEFAULT_PAPER_LIMITS in budget_manager.py with settings reads.
  Files in scope:
    - backend/config.py (add ~8 new fields)
    - backend/pipeline/compaction/budget_manager.py (replace hardcoded dicts)
    - backend/tests/test_pipeline/test_batch139_budgets.py (new)
  Depends on:       None

  Required Tests:
    | Test ID          | Type     | Behavior Verified                          | Failure Mode                                | Falsified By                                           | Pass Criteria                                         |
    |:-----------------|:---------|:-------------------------------------------|:--------------------------------------------|:-------------------------------------------------------|:------------------------------------------------------|
    | TEST-139-01-01   | unit     | Config has budget fields with correct defaults | Budgets not configurable from env | Remove budget fields from config | BudgetManager reads settings and produces same dict as old DEFAULT_BUDGETS |
    | TEST-139-01-02   | unit     | Paper limits read from settings            | Paper counts hardcoded | Hardcode different values in budget_manager | BudgetManager._paper_limits matches settings values |
    | TEST-139-01-03   | unit     | Abstract char limits read from settings    | Char limits hardcoded | Change default values | 80 and 150 read from settings.compaction_abstract_chars_tight/loose |
    | TEST-139-01-04   | unit     | Budget override via env var works          | Env var ignored | Set EROCK_COMPACTION_STAGE_BUDGETS to custom JSON | Custom values override defaults |
    | TEST-139-01-05   | unit     | Malformed budget JSON falls back to defaults | Parse error crashes app | Set EROCK_COMPACTION_STAGE_BUDGETS to invalid JSON like "{broken" | Graceful fallback to hardcoded defaults, no exception |

  Acceptance Criteria:
    AC-01-01: config.py has fields for stage budgets, paper limits, abstract chars
    AC-01-02: budget_manager.py reads from settings, no hardcoded dicts
    AC-01-03: Default values match current hardcoded values exactly (HB-01)
    AC-01-04: Override via env var produces different values

  Traceability:
    AC-01-01 → TEST-139-01-01, TEST-139-01-02, TEST-139-01-03
    AC-01-02 → TEST-139-01-01, TEST-139-01-02
    AC-01-03 → TEST-139-01-01
    AC-01-04 → TEST-139-01-04

TASK-02: BATCH-139/TASK-02 — Externalize constraint config
  Priority:          Medium
  Description:      Add config.py fields for ConstraintConfig values
                    (max_size, max_growth_pct, min_sections, allow_empty).
                    Replace hardcoded values in orchestrator.py line 458.
  Files in scope:
    - backend/config.py (add 4 new fields)
    - backend/pipeline/orchestrator.py (replace ConstraintConfig hardcoded values)
    - backend/tests/test_pipeline/test_batch139_constraints.py (new)
  Depends on:       TASK-01 (config.py changes)

  Required Tests:
    | Test ID          | Type     | Behavior Verified                          | Failure Mode                                | Falsified By                                           | Pass Criteria                                         |
    |:-----------------|:---------|:-------------------------------------------|:--------------------------------------------|:-------------------------------------------------------|:------------------------------------------------------|
    | TEST-139-02-01   | unit     | Config has constraint fields with defaults | Constraint values hardcoded in orchestrator | Remove fields from config | Settings has constraint_max_size=5000, constraint_max_growth_pct=0.3, constraint_min_sections=3, constraint_allow_empty=False |
    | TEST-139-02-02   | unit     | Orchestrator reads constraint from settings | Hardcoded values used | Change default in orchestrator back to hardcoded | ConstraintConfig built from settings, not literals |
    | TEST-139-02-03   | unit     | Constraint override via env var works      | Env var ignored | Set EROCK_CONSTRAINT_MAX_SIZE=10000 | ConstraintConfig uses overridden value |

  Acceptance Criteria:
    AC-02-01: config.py has constraint_max_size, constraint_max_growth_pct,
              constraint_min_sections, constraint_allow_empty fields
    AC-02-02: orchestrator.py line 458 reads from settings
    AC-02-03: Default values match current hardcoded values (5000, 0.3, 3, False)

  Traceability:
    AC-02-01 → TEST-139-02-01
    AC-02-02 → TEST-139-02-02
    AC-02-03 → TEST-139-02-01

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: All new config fields have defaults matching current hardcoded values (HB-01)
  BAC-02: Zero regressions in existing tests (HB-02)
  BAC-03: CHANGELOG.md updated with BATCH-139 entry.
  BAC-04: All documents archived under /docs/aiv/BATCH-139/.

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Reviewer Report ID:       REVIEW-BATCH-139-2026-05-10
Review Cycle:             1
Lead Decision:            [x] ACCEPT WITH MODIFICATIONS

All 3 flags acted on:
  CHK-14 (LOW) → Fixed: Expected delta corrected from +8 to +9
    (added TEST-139-01-05 for malformed JSON error path).
  CHK-19 (LOW) → Fixed: StageTokenBudget keyword args corrected
    from min/max to min_budget/max_budget in Data Models section.
  CHK-23 (LOW) → Fixed: Added TEST-139-01-05 (malformed JSON
    budget env var → graceful fallback). Covers the parse failure
    mode introduced by AUTH-02 JSON-string approach.

Blueprint Version after response: 1.1
Lead Sign:                ivory-wolf — 2026-05-10 01:40

═══════════════════════════════════════════════════════════
