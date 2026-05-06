BATCH BLUEPRINT — BATCH-82
═══════════════════════════════════════════════════════════
Batch ID: BATCH-82 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-06 | Sequencing: SEQUENTIAL
───────────────────────────────────────────────────────────
GOAL: Create a persistent knowledge library that indexes papers, gaps,
and ideas from completed pipeline runs. Future runs query this library
first before hitting external sources. Research compounds over time.
───────────────────────────────────────────────────────────
SCOPE:
  MUST: KnowledgeLibrary indexes papers/gaps/ideas per domain
  MUST: Future runs query existing knowledge first
  MUST: New papers added incrementally (dedup by DOI/title)
  MUST NOT: Delete or modify past run data
  MUST NOT: Require new DB migrations (use ChromaDB collections)
───────────────────────────────────────────────────────────
HARD BOUNDARIES:
  HB-01: MUST NOT delete or modify any existing pipeline run data
  HB-02: Dedup by DOI/title similarity before inserting
  HB-03: Library query failure MUST NOT crash pipeline
───────────────────────────────────────────────────────────
LINT: python -m ruff check backend/ && python -m pytest --co -q
───────────────────────────────────────────────────────────
STATE.md: Updated BATCH-81 | 0 batches since
───────────────────────────────────────────────────────────
TEST BASELINE: 1,998 | Delta: +12 | Expected: 2,010
───────────────────────────────────────────────────────────
TASK-01: KnowledgeLibrary Core (Critical)
  Files: backend/pipeline/knowledge/library.py (NEW)
  Tests: 8 tests

TASK-02: Library Indexer + Query (High)
  Files: backend/pipeline/knowledge/library_indexer.py (NEW)
  Tests: 4 tests
───────────────────────────────────────────────────────────
BAC-01: Papers/gaps/ideas indexed per domain
BAC-02: Dedup works by DOI/title
BAC-03: Query returns relevant past results
BAC-04: CHANGELOG.md updated
BAC-05: All docs under /docs/aiv/BATCH-82/
═══════════════════════════════════════════════════════════
