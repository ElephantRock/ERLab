# BATCH-26 Execution Plan

## Overview
Autonomous dashboard with cycle monitoring, start/stop, consciousness state visualization, and history.

## TASK-01: Backend — Autonomous History + Stop Endpoints

### Changes
1. **`backend/api/routes/pipeline.py`** — Add two new endpoints:
   - `POST /autonomous/stop` — Stops a running autonomous cycle via cancel event, returns `{status: "stopped"}`
   - `GET /autonomous/history` — Returns list of past autonomous cycles from `_progress_queues` keys + completed tasks
   - Internal tracking dict `_autonomous_cycles` to store cycle metadata (domain, runs, status)

### Tests (5)
- `backend/tests/test_api/test_autonomous_stop_history.py`
  - TEST-26-01-01: POST /autonomous/stop stops running cycle
  - TEST-26-01-02: GET /autonomous/history returns cycle list
  - TEST-26-01-03: History shows cycle status (running/completed/stopped)
  - TEST-26-01-04: Stop non-existent cycle returns 404
  - TEST-26-01-05: Scheduler status returns state info

### Commit: `feat(batch-26/task-01): add autonomous stop and history endpoints`

---

## TASK-02: Frontend — Autonomous Dashboard Components

### New Files
1. **`frontend/src/api/autonomous.ts`** — API client for autonomous endpoints
   - `startCycle(domain, maxRuns)`, `stopCycle(cycleId)`, `getHistory()`
   - Types: `AutonomousCycleHistory`

2. **`frontend/src/components/autonomous/cycle-progress.tsx`** — Cycle progress component
   - Shows cycle_id, domain, status, progress bar

3. **`frontend/src/components/autonomous/consciousness-state.tsx`** — Consciousness state badge
   - Displays current state (idle/exploring/generating/etc.) with color-coded badge

### Tests (3)
- `frontend/src/api/__tests__/autonomous.test.ts` — TEST-26-02-01
- `frontend/src/components/autonomous/__tests__/cycle-progress.test.tsx` — TEST-26-02-02
- `frontend/src/components/autonomous/__tests__/consciousness-state.test.tsx` — TEST-26-02-03

### Commit: `feat(batch-26/task-02): add autonomous dashboard components`

---

## TASK-03: Frontend — Autonomous Dashboard Page

### New/Modified Files
1. **`frontend/src/pages/autonomous.tsx`** — Main dashboard page
   - Start cycle form (domain + max_runs)
   - Stop button with confirmation dialog (HB-01)
   - History list
   - Consciousness state display

2. **`frontend/src/App.tsx`** — Add route: `/autonomous`
3. **`frontend/src/components/layout/sidebar.tsx`** — Add nav item with `Cpu` icon from lucide-react

### Tests (5)
- `frontend/src/pages/__tests__/autonomous.test.tsx`
  - TEST-26-03-01: Page renders with cycle controls
  - TEST-26-03-02: Start cycle form visible
  - TEST-26-03-03: Stop button requires confirmation
  - TEST-26-03-04: History list renders
  - TEST-26-03-05: Consciousness state displayed

### Commit: `feat(batch-26/task-03): add autonomous cycle dashboard page`

---

## HB-01 Compliance
Stop requires frontend confirmation dialog (AlertDialog pattern) before calling the stop endpoint.

## Finalization
- Update `docs/aiv/BATCH-26/REPORT.md`
- Update `CHANGELOG.md`
