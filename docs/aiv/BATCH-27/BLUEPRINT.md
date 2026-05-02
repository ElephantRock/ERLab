BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-27
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead
Date Issued:              2026-05-02

BATCH GOAL: Self-improvement section in settings. Scheduler controls on autonomous page.

HB-01: Evolution parameters are READ-ONLY in the UI. No manual parameter editing.

DATA MODELS:
  Existing: GET /api/v1/status/detailed includes self_improve_enabled
  EvolutionEngine (backend/pipeline/self_improve/engine.py)
  POST /api/v1/pipeline/scheduler/start + /stop + GET /status

  NEW: GET /api/v1/status/evolution → {enabled, overlays_generated, recent_outcomes}

DEPENDENCY: BATCH-26
BASELINE: ~1,770 | Delta: +10 (3 backend + 7 frontend) | Target: ~1,780

TASK LIST (SEQUENTIAL):
───────────────────────────────────────────────────────────

TASK-01: Backend — Evolution Status Endpoint
  Files: backend/api/routes/status.py (MODIFY — add /evolution endpoint)
  Tests: TEST-27-01-01: GET /status/evolution returns evolution info
         TEST-27-01-02: Evolution disabled returns appropriate status
         TEST-27-01-03: Evolution enabled shows overlay count
  Commit: feat(batch-27/task-01): add evolution status endpoint

TASK-02: Frontend — Self-Improvement Settings + Scheduler Controls
  Files: frontend/src/pages/settings.tsx (MODIFY — add self-improve section)
         frontend/src/pages/autonomous.tsx (MODIFY — add scheduler controls)
         frontend/src/api/autonomous.ts (MODIFY — add evolution fetch)
  Tests: TEST-27-02-01: Settings shows self-improve section (read-only)
         TEST-27-02-02: Autonomous page shows scheduler start/stop
         TEST-27-02-03: Evolution status displayed
         TEST-27-02-04: Scheduler start calls API
         TEST-27-02-05: Scheduler stop calls API
         TEST-27-02-06: Scheduler status displayed
         TEST-27-02-07: No edit controls for evolution params (HB-01)
  Commit: feat(batch-27/task-02): add self-improve and scheduler UI

BAC: BAC-01 ✓ | BAC-02 ✓ | BAC-03 ✓
LEAD RESPONSE: Inline review. ACCEPT.
Lead Sign: Lead + 2026-05-02 10:15

═══════════════════════════════════════════════════════════
