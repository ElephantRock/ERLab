BATCH BLUEPRINT — BATCH-85
═══════════════════════════════════════════════════════════
Batch ID: BATCH-85 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-06 | Sequencing: SEQUENTIAL
───────────────────────────────────────────────────────────
GOAL: Add Semantic Scholar, PubMed, and CrossRef as literature sources.
Create MultiSourceSearcher that fans out queries across all engines
and merges/deduplicates results.
───────────────────────────────────────────────────────────
SCOPE:
  MUST: SemanticScholarSource fully implemented (not stub)
  MUST: PubMedSource with NCBI E-utilities API
  MUST: CrossRefSource for DOI-based metadata
  MUST: MultiSourceSearcher fans out and merges
  MUST NOT: Break existing OpenAlex + arXiv sources
  MUST NOT: Require API keys (graceful degradation)
───────────────────────────────────────────────────────────
HARD BOUNDARIES:
  HB-01: Each source fails independently (no cascade failures)
  HB-02: Existing OpenAlex/arXiv behavior unchanged
  HB-03: No API key required — optional enhancement only
───────────────────────────────────────────────────────────
LINT: python -m ruff check backend/ && python -m pytest --co -q
───────────────────────────────────────────────────────────
STATE.md: Updated BATCH-84 | 0 batches since
───────────────────────────────────────────────────────────
TEST BASELINE: 2,028 | Delta: +14 | Expected: 2,042
───────────────────────────────────────────────────────────
TASK-01: Three New Sources (Critical)
  Files: backend/pipeline/literature/semantic_scholar.py (MODIFY — currently stub),
         backend/pipeline/literature/pubmed_source.py (NEW),
         backend/pipeline/literature/crossref_source.py (NEW)
  Tests: 9 tests

TASK-02: MultiSourceSearcher (High)
  Files: backend/pipeline/literature/multi_source.py (NEW)
  Tests: 5 tests
───────────────────────────────────────────────────────────
BAC-01: 3 new literature sources functional
BAC-02: MultiSourceSearcher merges results from all sources
BAC-03: Each source fails independently
BAC-04: CHANGELOG.md updated
BAC-05: All docs under /docs/aiv/BATCH-85/
═══════════════════════════════════════════════════════════
