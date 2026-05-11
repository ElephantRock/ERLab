BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-162
Blueprint Version:        1.0 (Lead-Reviewed, Direct Implementation)
Cycle Mode:               STANDARD (§5.3 Lead Override)

BATCH GOAL
───────────────────────────────────────────────────────────
Wire journal into pipeline stages. Add API to retrieve journals.
Add AI honesty labeling to journal output.

HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: All 2,643 pre-existing tests pass.
  HB-02: Journal failure MUST NOT block pipeline.

TASKS
───────────────────────────────────────────────────────────
TASK-01: Journal API endpoint (4 tests)
  - GET /api/v1/pipeline/runs/{run_id}/journal → returns notes + readme
  - Returns 404 if no journal exists

TASK-02: AI Honesty labeling in journal (3 tests)
  - Journal README.md includes AI_HONESTY_BADGE
  - Notes.md includes disclaimer header
  - Writers track AI generation metadata

TASK-03: Per-stage journal hooks in stages (3 tests)
  - LiteratureSearchStage: journal note with paper count
  - GapReflectionStage: journal note with reflection score
  - ExportStage: journal note with file paths

TEST BASELINE: 2,643 → 2,653 (+10)
═══════════════════════════════════════════════════════════
