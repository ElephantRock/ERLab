BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-26
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead
Date Issued:              2026-05-02

BATCH GOAL: Autonomous dashboard with cycle monitoring, start/stop,
consciousness state visualization, and history.

HB-01: Autonomous stop requires confirmation. No silent termination.

DATA MODELS:
  Existing endpoints:
    POST /api/v1/pipeline/autonomous → {cycle_id, status, domain, max_runs}
    POST /api/v1/pipeline/scheduler/start → {status}
    POST /api/v1/pipeline/scheduler/stop → {status}
    GET  /api/v1/pipeline/scheduler/status → {running, ...}

  NEW endpoints:
    POST /api/v1/pipeline/autonomous/stop → {status: "stopped"}
    GET  /api/v1/pipeline/autonomous/history → [{cycle_id, domain, runs, status}]

  ConsciousnessState enum: idle, exploring, generating, evaluating, synthesizing, resting

DEPENDENCY: BATCH-25
BASELINE: ~1,757 | Delta: +13 (5 backend + 8 frontend) | Target: ~1,770

TASK LIST (SEQUENTIAL):
───────────────────────────────────────────────────────────

TASK-01: Backend — Autonomous History + Stop Endpoints
  Files: backend/api/routes/pipeline.py (MODIFY)
  Tests: TEST-26-01-01: POST /autonomous/stop stops running cycle
         TEST-26-01-02: GET /autonomous/history returns cycle list
         TEST-26-01-03: History shows cycle status (running/completed/stopped)
         TEST-26-01-04: Stop non-existent cycle returns 404
         TEST-26-01-05: Scheduler status returns state info
  Commit: feat(batch-26/task-01): add autonomous stop and history endpoints

TASK-02: Frontend — Autonomous Dashboard Components
  Files: frontend/src/api/autonomous.ts (NEW)
         frontend/src/components/autonomous/cycle-progress.tsx (NEW)
         frontend/src/components/autonomous/consciousness-state.tsx (NEW)
  Tests: TEST-26-02-01: API client calls correct endpoints
         TEST-26-02-02: CycleProgress renders cycle info
         TEST-26-02-03: ConsciousnessState shows current state badge
  Commit: feat(batch-26/task-02): add autonomous dashboard components

TASK-03: Frontend — Autonomous Dashboard Page
  Files: frontend/src/pages/autonomous.tsx (NEW — add as new page)
         frontend/src/App.tsx (MODIFY — add route)
         frontend/src/components/layout/sidebar.tsx (MODIFY — add nav item)
  Tests: TEST-26-03-01: Page renders with cycle controls
         TEST-26-03-02: Start cycle form visible
         TEST-26-03-03: Stop button requires confirmation
         TEST-26-03-04: History list renders
         TEST-26-03-05: Consciousness state displayed
  Commit: feat(batch-26/task-03): add autonomous cycle dashboard page

BAC: BAC-01 Autonomous dashboard works | BAC-02 CHANGELOG | BAC-03 docs
LEAD RESPONSE: Inline review. ACCEPT.
Lead Sign: Lead + 2026-05-02 09:50

═══════════════════════════════════════════════════════════
