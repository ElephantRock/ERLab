# BATCH-126 BLUEPRINT — Method-Problem Gap Matrix

```
Batch ID:                 BATCH-126
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-09

BATCH GOAL
Create a MethodProblemDetector that builds a method×problem applicability matrix.
For each METHOD claim and each dataset/problem from RESULT claims, check if
the method has been applied. If not, score the gap by applicability.

LINT COMMAND
  python -m pytest backend/tests/test_pipeline/test_batch126_method_problem.py -v --tb=short 2>&1 | tail -5

HARD BOUNDARIES
  HB-01: Returns [] on empty claims. HB-02: Only METHOD + RESULT claims considered.

DATA MODELS
  MethodProblemGap (dataclass):
    - method_name: str
    - method_paper_id: str
    - problem_dataset: str
    - applicability_score: float (0-1)
    - reasoning: str

  MethodProblemDetector:
    - find_gaps(self, claims: list[Claim]) -> list[MethodProblemGap]
    - _build_matrix(self, claims) -> dict[tuple, bool]
    - _score_gap(self, method_name, dataset) -> float

TEST BASELINE: 2,337 | Delta: +6 | Expected: 2,343

TASK-01: MethodProblemDetector
  Tests:
  | TEST-126-01-01 | unit | MethodProblemGap creates | TypeError | Create gap | No error |
  | TEST-126-01-02 | unit | find_gaps returns [] on empty (HB-01) | Crash | [] | Returns [] |
  | TEST-126-01-03 | unit | Known method-dataset pairs excluded | Pair included | Method already on dataset | Not in gaps |
  | TEST-126-01-04 | unit | Novel method-dataset pairs flagged | Not flagged | New combo | In gaps list |
  | TEST-126-01-05 | unit | Only METHOD+RESULT claims used (HB-02) | LIMITATION used | Mixed types | Only METHOD+RESULT |
  | TEST-126-01-06 | unit | Gaps scored by applicability | Score 0 | Novel combo | applicability_score > 0 |

BAC-01: All 6 tests pass
BAC-02: MethodProblemDetector identifies unexplored method-dataset combinations
