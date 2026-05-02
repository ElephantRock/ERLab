BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID: BATCH-33 | Version: 1.0 | STANDARD | Lead | 2026-05-02

BATCH GOAL: PDF export, bulk export, plugin marketplace UI.

TASK-01: Backend — PDF Export + Plugin Registry
  Files: backend/api/routes/exports.py (NEW — PDF + bulk export)
         backend/plugins/registry.py (NEW — plugin registry)
         backend/api/routes/plugins.py (NEW — list/install plugins)
  Tests: TEST-33-01-01: POST /export/pdf returns PDF content
         TEST-33-01-02: POST /export/bulk returns zip of ideas
         TEST-33-01-03: GET /plugins lists available plugins
         TEST-33-01-04: POST /plugins/install registers plugin
  Commit: feat(batch-33/task-01)

TASK-02: Frontend — Export Dialog + Plugins Page
  Files: frontend/src/components/export/export-dialog.tsx (NEW)
         frontend/src/pages/plugins.tsx (NEW — replaces /settings placeholder usage)
  Tests: TEST-33-02-01: Export dialog shows format options
         TEST-33-02-02: PDF export triggers download
         TEST-33-02-03: Plugins page lists available plugins
         TEST-33-02-04: Install button installs plugin
  Commit: feat(batch-33/task-02)

TASK-03: Frontend — Idea Detail Export Button
  Files: frontend/src/pages/idea-detail.tsx (MODIFY — add export button)
         frontend/src/pages/ideas-browser.tsx (MODIFY — bulk export)
  Tests: TEST-33-03-01: Idea detail has export button
         TEST-33-03-02: Bulk export in ideas browser
  Commit: feat(batch-33/task-03)

DEPENDENCY: BATCH-32
BASELINE: ~1,830 | Delta: +10 | Target: ~1,840
BAC: ✓ | Lead Sign: Lead + 2026-05-02 12:10
═══════════════════════════════════════════════════════════
