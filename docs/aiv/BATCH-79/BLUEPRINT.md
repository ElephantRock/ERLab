BATCH BLUEPRINT — BATCH-79
═══════════════════════════════════════════════════════════
Batch ID: BATCH-79 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-06 | Sequencing: SEQUENTIAL
───────────────────────────────────────────────────────────
GOAL: Replace coarse "Stage 3/7 complete" SSE events with granular,
human-readable progress messages showing what the LLM is doing.
───────────────────────────────────────────────────────────
SCOPE:
  MUST: Each stage emits granular SSE events during execution
  MUST: Events include stage, step, message, progress_pct, timestamp
  MUST: Frontend displays messages in scrollable activity log
  MUST NOT: Change existing stage_start/stage_complete events
  MUST NOT: Expose internal prompts, API keys, or raw state
  MUST NOT: Slow down pipeline (non-blocking emission)
───────────────────────────────────────────────────────────
HARD BOUNDARIES:
  HB-01: Existing SSE event format MUST NOT change (backward compatible)
  HB-02: Messages MUST NOT contain API keys or raw prompts
  HB-03: Message emission MUST be non-blocking
───────────────────────────────────────────────────────────
LINT: python -m ruff check backend/ && python -m pytest --co -q
───────────────────────────────────────────────────────────
STATE.md: Updated BATCH-78 | 0 batches since
───────────────────────────────────────────────────────────
TEST BASELINE: 1,960 | Delta: +12 | Expected: 1,972
───────────────────────────────────────────────────────────
TASK-01: ProgressReporter + Event Model (Critical)
  Files: backend/pipeline/streaming/events.py (MODIFY),
         backend/pipeline/streaming/progress_reporter.py (NEW),
         backend/pipeline/streaming/manager.py (MODIFY)
  Tests: 7 tests (event model, reporter, SSE broadcast)

TASK-02: Stage Integration + Frontend Activity Log (High)
  Files: backend/pipeline/orchestrator.py (MODIFY),
         frontend/src/components/pipeline/activity-log.tsx (NEW),
         frontend/src/pages/run-detail.tsx (MODIFY),
         frontend/src/hooks/usePipelineProgress.ts (MODIFY)
  Tests: 5 tests (stage emissions, no sensitive data)
───────────────────────────────────────────────────────────
BAC-01: Pipeline emits granular messages visible in frontend
BAC-02: Existing SSE events unchanged
BAC-03: No sensitive data in messages
BAC-04: CHANGELOG.md updated
BAC-05: All docs under /docs/aiv/BATCH-79/
═══════════════════════════════════════════════════════════
