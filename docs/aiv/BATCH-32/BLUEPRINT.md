BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID: BATCH-32 | Version: 1.0 | STANDARD | Lead | 2026-05-02

BATCH GOAL: Dashboard lazy loading, gaps pagination, DB indexes, webhook notifications.
HB-01: Dashboard MUST render in under 3 seconds with 1000+ ideas.

TASK-01: Backend — DB Indexes + Webhook Notifications
  Files: backend/db/models.py (MODIFY — add indexes)
         backend/api/routes/pipeline.py (MODIFY — webhook on completion)
         backend/notifications/ (NEW — webhook module)
  Tests: TEST-32-01-01: Indexes exist on frequently queried columns
         TEST-32-01-02: Webhook fires on pipeline completion
         TEST-32-01-03: Webhook payload includes run summary
         TEST-32-01-04: Webhook failure doesn't block pipeline
  Commit: feat(batch-32/task-01): add DB indexes and webhook notifications

TASK-02: Frontend — Lazy Loading + Pagination
  Files: frontend/src/pages/dashboard.tsx (MODIFY — lazy load charts)
         frontend/src/pages/gaps-explorer.tsx (MODIFY — pagination)
         frontend/src/pages/ideas-browser.tsx (MODIFY — pagination)
  Tests: TEST-32-02-01: Dashboard lazy loads chart components
         TEST-32-02-02: Gaps explorer paginates results
         TEST-32-02-03: Ideas browser paginates results
         TEST-32-02-04: Pagination controls work (next/prev)
  Commit: feat(batch-32/task-02): add lazy loading and pagination

DEPENDENCY: BATCH-31
BASELINE: ~1,822 | Delta: +8 | Target: ~1,830
BAC: ✓ | Lead Sign: Lead + 2026-05-02 11:40
═══════════════════════════════════════════════════════════
