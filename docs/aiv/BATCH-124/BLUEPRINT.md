# BATCH-124 BLUEPRINT — Curation Rules Engine

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-124
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-09
Review SLA:               30 min
Execution SLA per Task:   60 min

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Create a CurationEngine that applies user-defined rules to filter and rank papers.
Rules: must_include (author, keyword, venue), must_exclude (keyword),
semantic_threshold (cosine similarity), max_papers_per_day.

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  python -m pytest backend/tests/test_pipeline/test_batch124_curation.py -v --tb=short 2>&1 | tail -5

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: CurationEngine.filter() MUST return empty list (not crash) on empty input.
  HB-02: Rules with invalid fields MUST be skipped with a warning, not raise.

───────────────────────────────────────────────────────────
DATA MODELS
───────────────────────────────────────────────────────────

  CurationRule (dataclass):
    - rule_id: str
    - rule_type: str  (must_include | must_exclude | semantic_threshold | max_papers)
    - field: str      (keyword | author | venue | abstract)
    - value: str | float
    - enabled: bool = True

  CurationEngine:
    - __init__(self, rules: list[CurationRule], embedding_service=None)
    - filter(self, papers: list[dict]) -> list[dict]
    - score(self, paper: dict) -> float
    - _apply_rule(self, paper: dict, rule: CurationRule) -> bool

  File layout:
    backend/pipeline/curation/
      __init__.py
      models.py
      engine.py

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline: 2,324
  Expected delta: +6
  Expected total: 2,330

───────────────────────────────────────────────────────────
TASK-01: CurationRule Model + CurationEngine
  Priority: Critical
  Files: backend/pipeline/curation/ (3 new), tests (1 new)
  Tests:
  | TEST-124-01-01 | unit | CurationRule creates with all fields | TypeError | Create rule | No error |
  | TEST-124-01-02 | unit | filter returns empty on empty input (HB-01) | Crash | filter([]) | Returns [] |
  | TEST-124-01-03 | unit | must_include keyword matches | No match | Include "transformer" rule | Matching papers pass |
  | TEST-124-01-04 | unit | must_exclude keyword removes | Not removed | Exclude "survey" rule | Survey papers removed |
  | TEST-124-01-05 | unit | Invalid rule skipped (HB-02) | Exception raised | Add bad rule | Warning logged, no crash |
  | TEST-124-01-06 | unit | max_papers limits output | All returned | max_papers=2 with 5 papers | Only 2 returned |

BAC-01: All 6 tests pass
BAC-02: CurationEngine filters papers correctly
BAC-03: Documents archived under /docs/aiv/BATCH-124/
