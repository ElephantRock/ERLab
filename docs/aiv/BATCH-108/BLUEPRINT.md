BATCH BLUEPRINT — BATCH-108
═══════════════════════════════════════════════════════════
Batch ID: BATCH-108 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-07
───────────────────────────────────────────────────────────
GOAL: In-app notification system (pipeline completed, errors)
+ Markdown/BibTeX file export (download endpoint).
───────────────────────────────────────────────────────────
TEST BASELINE: 2,213 | Delta: +8 | Expected: 2,221
───────────────────────────────────────────────────────────
TASK-01: NotificationService (High)
  Files: backend/pipeline/notifications/service.py (NEW)
  Tests: 4 tests

TASK-02: Markdown/BibTeX Export Endpoint (High)
  Files: backend/api/routes/export.py (NEW)
  Tests: 4 tests
───────────────────────────────────────────────────────────
═══════════════════════════════════════════════════════════
