# BATCH-125 BLUEPRINT — Contradiction Detector

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-125
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-09
Review SLA:               30 min
Execution SLA per Task:   60 min

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Create a ContradictionDetector that finds conflicting claims across papers.
Query claims with same metric + dataset but different values. Use LLM to
verify genuine contradiction vs. legitimate variation.

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  python -m pytest backend/tests/test_pipeline/test_batch125_contradiction.py -v --tb=short 2>&1 | tail -5

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: ContradictionDetector MUST return [] on failure, not crash.
  HB-02: Only RESULT claims with same dataset + metric are candidates.

───────────────────────────────────────────────────────────
DATA MODELS
───────────────────────────────────────────────────────────

  ContradictionCandidate (dataclass):
    - claim_a: Claim
    - claim_b: Claim
    - metric: str
    - dataset: str
    - value_a: str
    - value_b: str
    - is_genuine: bool | None  (None = not yet verified)
    - explanation: str

  ContradictionDetector:
    - __init__(self, claim_store: ClaimStore, provider=None)
    - find_contradictions(self, claims: list[Claim]) -> list[ContradictionCandidate]
    - _find_candidates(self, claims: list[Claim]) -> list[ContradictionCandidate]
    - _verify_contradiction(self, candidate: ContradictionCandidate) -> ContradictionCandidate

  Files:
    backend/pipeline/claims/contradiction/__init__.py
    backend/pipeline/claims/contradiction/detector.py
    backend/pipeline/claims/contradiction/models.py

───────────────────────────────────────────────────────────
TEST BASELINE: 2,330 | Delta: +7 | Expected: 2,337

TASK-01: ContradictionCandidate + ContradictionDetector
  Priority: Critical
  Tests:
  | TEST-125-01-01 | unit | ContradictionCandidate creates | TypeError | Create candidate | No error |
  | TEST-125-01-02 | unit | find_candidates pairs same metric+dataset | Wrong pairs | Same metric, different datasets | Only same-dataset pairs |
  | TEST-125-01-03 | unit | find_contradictions returns [] on failure (HB-01) | Crash | Empty claims list | Returns [] |
  | TEST-125-01-04 | unit | Only RESULT claims are candidates (HB-02) | METHOD claims included | Pass mixed types | Only RESULT paired |
  | TEST-125-01-05 | unit | Different values flagged as candidate | Same values flagged | Same metric, different values | Candidate created |
  | TEST-125-01-06 | unit | LLM verification marks genuine vs spurious | All flagged | Known non-contradiction | is_genuine=False |
  | TEST-125-01-07 | integ | End-to-end: 6 claims → 1 contradiction | No contradiction | 3 papers same metric | 1 genuine contradiction |

BAC-01: All 7 tests pass
BAC-02: ContradictionDetector finds and verifies cross-paper contradictions
BAC-03: Documents archived under /docs/aiv/BATCH-125/
