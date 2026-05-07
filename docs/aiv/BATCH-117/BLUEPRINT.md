# BATCH-117 BLUEPRINT — Cross-Run Gap Deduplication

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-117
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-07

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Add cross-run gap deduplication so overlapping gaps from different
pipeline runs are merged rather than counted as separate discoveries.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Create GapDeduplicator with word-overlap similarity (threshold 0.6)
  - Store canonical gap + merge metadata (source_run_ids)
  - Support single-run and multi-run deduplication

What the code MUST NOT do:
  - Must NOT delete original gap records (they stay per-run)
  - Must NOT modify the gap analyzer

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Deduplication must not lose unique gaps (only merge near-duplicates)

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  python -m pytest --co -q 2>&1 | tail -1

───────────────────────────────────────────────────────────
DATA MODELS
───────────────────────────────────────────────────────────
  New: backend/pipeline/gap_analysis/deduplicator.py
  Classes: GapDeduplicator, MergedGap (with source_run_ids, occurrence_count)

───────────────────────────────────────────────────────────
STATE.md STATUS: [x] YES, updated 2026-05-07

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline: 2,281  Expected delta: +7  Expected total: 2,288

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: Create GapDeduplicator
  Priority:          High
  Files in scope: backend/pipeline/gap_analysis/deduplicator.py (NEW)
  Required Tests:
    | Test ID         | Type | Behavior Verified              | Failure Mode          | Falsified By               | Pass Criteria              |
    |:----------------|:-----|:-------------------------------|:----------------------|:---------------------------|:---------------------------|
    | TEST-117-01-01  | unit | Identical gaps merged          | Not merged            | Set threshold to 1.0       | len(deduped) < len(input)  |
    | TEST-117-01-02  | unit | Unique gaps preserved (HB-01)  | Unique lost           | Add unique gap             | unique gap in result       |
    | TEST-117-01-03  | unit | Similar titles merged          | Not merged            | Set threshold to 1.0       | merged count >= 1          |
    | TEST-117-01-04  | unit | Source run IDs in metadata     | Metadata lost         | Skip metadata write        | source_run_ids present     |
    | TEST-117-01-05  | unit | Empty input returns empty      | Crash on []           | Pass []                    | result == []               |
    | TEST-117-01-06  | unit | Single gap returns unchanged   | Single merged         | Pass 1 gap                 | len(result) == 1           |
    | TEST-117-01-07  | unit | Dedup works across 3+ runs    | Only works for 2      | Pass gaps from 3 runs      | Correct merge count        |
  Acceptance Criteria:
    AC-01: GapDeduplicator merges near-duplicate gaps
    AC-02: Unique gaps preserved (HB-01)
    AC-03: Multi-run deduplication supported
  Traceability:
    AC-01 → TEST-117-01-01, TEST-117-01-03
    AC-02 → TEST-117-01-02, TEST-117-01-05, TEST-117-01-06
    AC-03 → TEST-117-01-04, TEST-117-01-07

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: GapDeduplicator merges near-duplicate gaps
  BAC-02: All 7 tests pass
  BAC-03: CHANGELOG.md updated
  BAC-04: Documents archived under /docs/aiv/BATCH-117/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Reviewer Report ID: REVIEW-BATCH-117-2026-05-07
Review Cycle: 1
Lead Decision: [x] ACCEPT
2 flags (stale baseline). Accepted.
Lead Sign: ivory-wolf — 2026-05-07

═══════════════════════════════════════════════════════════
```
