BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID: BATCH-31 | Version: 1.0 | STANDARD | Lead | 2026-05-02

BATCH GOAL: SSE header-based auth. Mobile responsive layout.
HB-01: API keys MUST NOT appear in URLs after this Batch.

TASK-01: SSE Auth Fix
  Files: frontend/src/api/pipeline.ts (MODIFY — custom fetch-based SSE with auth header)
         backend/api/routes/pipeline.py (MODIFY — validate SSE auth header)
  Tests: TEST-31-01-01: SSE includes Authorization header
         TEST-31-01-02: SSE rejects without auth when auth_enabled
         TEST-31-01-03: SSE works without auth when auth_enabled=False
         TEST-31-01-04: No API key in URL query params
  Commit: feat(batch-31/task-01): add header-based auth to SSE stream

TASK-02: Responsive Design
  Files: frontend/src/components/layout/sidebar.tsx (MODIFY — mobile bottom nav)
         frontend/src/components/layout/app-layout.tsx (MODIFY — responsive grid)
         frontend/src/index.css (MODIFY — responsive breakpoints)
  Tests: TEST-31-02-01: Sidebar collapses on mobile viewport
         TEST-31-02-02: Bottom nav renders on mobile
         TEST-31-02-03: Dashboard grid adapts to screen width
         TEST-31-02-04: Pages remain usable at 375px width
  Commit: feat(batch-31/task-02): add responsive layout for mobile

DEPENDENCY: BATCH-29, BATCH-30
BASELINE: ~1,814 | Delta: +8 frontend | Target: ~1,822
BAC: ✓ | Lead Sign: Lead + 2026-05-02 11:40
═══════════════════════════════════════════════════════════
