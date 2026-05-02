BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-23
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead
Date Issued:              2026-05-02

BATCH GOAL: Literature search page with multi-source academic search, paper cards, ingestion into knowledge base.

SCOPE:
  MUST: Create backend API route for literature search, create frontend page with
        search input, paper cards showing title/authors/abstract/year, ingest button
  MUST NOT: Modify existing literature pipeline modules (search_service, sources)

HB-01: Literature search endpoint is READ-ONLY for search. Ingestion requires user confirmation.

DATA MODELS:
  Backend literature service (backend/pipeline/literature/):
    SearchService.search_all(query, max_results) → list[Paper]
    Paper: {title, authors: list[Author], abstract, year, source, doi, url}
    Author: {name, affiliation}

  NEW endpoints:
    GET /api/v1/literature/search?q=...&max_results=10 → {papers: Paper[]}
    POST /api/v1/literature/ingest body:{paper: Paper} → {status: "ingested", id}

DEPENDENCY: BATCH-22
BASELINE: 1,719 tests | Delta: +12 (5 backend + 7 frontend) | Target: 1,731

TASK LIST (SEQUENTIAL):
───────────────────────────────────────────────────────────

TASK-01: Backend — Literature API Route
  Files: backend/api/routes/literature.py (NEW)
         backend/api/app.py (MODIFY — register route)
  Tests: TEST-23-01-01: GET /literature/search?q=test returns papers
         TEST-23-01-02: GET /literature/search without q returns 422
         TEST-23-01-03: POST /literature/ingest stores paper
         TEST-23-01-04: Ingestion confirmation required (paper must have title)
         TEST-23-01-05: Search handles source errors gracefully
  Commit: feat(batch-23/task-01): add literature search and ingest API endpoints

TASK-02: Frontend — Literature Search Page
  Files: frontend/src/api/literature.ts (NEW)
         frontend/src/components/literature/paper-card.tsx (NEW)
         frontend/src/pages/literature.tsx (NEW — replaces placeholder)
         frontend/src/App.tsx (MODIFY — route update)
  Tests: TEST-23-02-01: Literature page renders search input
         TEST-23-02-02: Search returns paper cards
         TEST-23-02-03: Paper card shows title, authors, year
         TEST-23-02-04: Ingest button requires confirmation
         TEST-23-02-05: Empty results shows message
         TEST-23-02-06: Search error handled
         TEST-23-02-07: API client calls correct endpoints
  Commit: feat(batch-23/task-02): add literature search page with paper cards

BAC: BAC-01 Literature search works | BAC-02 CHANGELOG | BAC-03 docs
LEAD RESPONSE: Inline review. literature/search_service.py verified.
New API route wraps existing pipeline service. ACCEPT.
Lead Sign: Lead + 2026-05-02 09:00

═══════════════════════════════════════════════════════════
