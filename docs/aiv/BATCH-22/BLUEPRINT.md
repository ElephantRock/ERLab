BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-22
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead
Date Issued:              2026-05-02

BATCH GOAL: Add session grouping for pipeline runs — backend filter by session_id,
frontend Sessions page showing runs grouped by session with session creation in pipeline form.

SCOPE:
  MUST: Add session_id query param to GET /runs endpoint, create sessions page
        showing runs grouped by session_id, add session_id input to pipeline form
  MUST NOT: Create a full session management system (no separate Session table)

NOTE: The platform has no dedicated session management. session_id is a string
field in the pipeline run request used for grouping. This Batch adds grouping UX.

HB-01: session_id is a simple string field, not a foreign key. No new DB tables.

DATA MODELS:
  PipelineRun has session_id: str | None in the create schema
  GET /api/v1/pipeline/runs?session_id=... → filtered list
  Frontend groups runs by session_id for display

DEPENDENCY: BATCH-16 (placeholder)
BASELINE: 1,707 tests | Delta: +12 (5 backend + 7 frontend) | Target: 1,719

TASK LIST (SEQUENTIAL):
───────────────────────────────────────────────────────────

TASK-01: Backend — Session Filter
  Files: backend/api/routes/pipeline.py (MODIFY — add session_id query param)
         backend/db/crud.py (MODIFY — filter by session_id)
  Tests: TEST-22-01-01: GET /runs?session_id=X returns filtered results
         TEST-22-01-02: GET /runs?session_id=nonexistent returns empty
         TEST-22-01-03: GET /runs without session_id returns all (existing behavior)
         TEST-22-01-04: GET /runs/list endpoint returns unique session_ids
         TEST-22-01-05: Session list endpoint returns [{session_id, run_count, latest_run_at}]
  Commit: feat(batch-22/task-01): add session grouping and filter to pipeline runs

TASK-02: Frontend — Sessions Page + Pipeline Form Session Input
  Files: frontend/src/api/sessions.ts (NEW)
         frontend/src/pages/sessions.tsx (NEW — replaces placeholder)
         frontend/src/pages/pipeline-new.tsx (MODIFY — add session_id input)
         frontend/src/App.tsx (MODIFY — route update)
  Tests: TEST-22-02-01: Sessions page renders grouped runs
         TEST-22-02-02: Click session shows filtered runs
         TEST-22-02-03: Pipeline form has session_id input
         TEST-22-02-04: Session card shows run count and latest date
         TEST-22-02-05: Empty sessions shows message
         TEST-22-02-06: New session input is optional
         TEST-22-02-07: API error handled
  Commit: feat(batch-22/task-02): add sessions page and pipeline session input

BAC: BAC-01 Sessions page shows grouped runs | BAC-02 CHANGELOG | BAC-03 docs
LEAD RESPONSE: Inline review. Rescoped from roadmap — no dedicated session table exists.
session_id is a simple string filter. ACCEPT.
Lead Sign: Lead + 2026-05-02 08:45

═══════════════════════════════════════════════════════════
