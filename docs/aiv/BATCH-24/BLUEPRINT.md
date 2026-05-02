BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-24
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead
Date Issued:              2026-05-02

BATCH GOAL: PDF upload via drag-and-drop, enriched knowledge stats display.

SCOPE:
  MUST: Add POST /knowledge/ingest endpoint for PDF upload, enrich GET /knowledge/stats
        with more detail, create frontend upload zone, update knowledge page stats
  MUST NOT: Modify existing knowledge search endpoint

HB-01: Uploaded files MUST be validated as PDF before processing. No executable uploads.

DATA MODELS:
  Existing: GET /knowledge/stats → stats summary
            POST /knowledge/search → search results
  NEW:      POST /knowledge/ingest (multipart/form-data, PDF file) → {status, filename, chunks}
            Enhanced /knowledge/stats → {total_documents, total_chunks, ...}

DEPENDENCY: BATCH-22
BASELINE: ~1,731 tests | Delta: +10 (4 backend + 6 frontend) | Target: ~1,741

TASK LIST (SEQUENTIAL):
───────────────────────────────────────────────────────────

TASK-01: Backend — PDF Ingest Endpoint + Enhanced Stats
  Files: backend/api/routes/knowledge.py (MODIFY)
  Tests: TEST-24-01-01: POST /ingest with valid PDF returns success
         TEST-24-01-02: POST /ingest with non-PDF returns 400
         TEST-24-01-03: POST /ingest with no file returns 422
         TEST-24-01-04: GET /stats returns enriched stats
  Commit: feat(batch-24/task-01): add PDF ingest endpoint and enriched stats

TASK-02: Frontend — Upload Zone + Stats Banner
  Files: frontend/src/components/knowledge/upload-zone.tsx (NEW)
         frontend/src/pages/knowledge-search.tsx (MODIFY — add upload zone + stats)
  Tests: TEST-24-02-01: Upload zone renders with drop area
         TEST-24-02-02: Drop PDF triggers ingest API call
         TEST-24-02-03: Non-PDF file shows error
         TEST-24-02-04: Stats banner shows document counts
         TEST-24-02-05: Upload progress shows loading state
         TEST-24-02-06: Upload success shows confirmation
  Commit: feat(batch-24/task-02): add PDF upload zone and enriched stats

BAC: BAC-01 PDF upload works | BAC-02 CHANGELOG | BAC-03 docs
LEAD RESPONSE: Inline review. ACCEPT.
Lead Sign: Lead + 2026-05-02 09:15

═══════════════════════════════════════════════════════════
