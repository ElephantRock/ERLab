BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-160
Blueprint Version:        1.0 (Lead-Reviewed, Direct Implementation)
Cycle Mode:               STANDARD (§5.3 Lead Override)

BATCH GOAL
───────────────────────────────────────────────────────────
Expand document ingestion beyond PDF to support TXT, CSV, DOCX.
Wire uploaded documents into pipeline as supplementary sources.

HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: All 2,619 pre-existing tests pass.
  HB-02: Invalid files MUST NOT crash pipeline or API.
  HB-03: Uploaded docs are supplementary, not primary pipeline input.

TASKS
───────────────────────────────────────────────────────────
TASK-01: Generic DocumentParser (PDF + TXT + CSV + DOCX) (5 tests)
  - Reuse PDFService for PDF
  - TXT: simple read + chunk
  - CSV: extract headers + sample rows → text
  - DOCX: python-docx extraction (with graceful fallback)
  - Unified parse_and_chunk() interface

TASK-02: Extended upload API (4 tests)
  - POST /api/v1/knowledge/ingest accepts any supported format
  - Magic-bytes validation for each format
  - GET /api/v1/knowledge/documents lists uploaded docs
  - Size limit: 50MB

TASK-03: Pipeline integration (3 tests)
  - Uploaded docs for a domain are injected into LiteratureSearchStage
  - They appear as source="local_upload" papers in ctx.all_papers
  - Counted in pipeline metadata

TEST BASELINE: 2,619 → 2,631 (+12)
═══════════════════════════════════════════════════════════
