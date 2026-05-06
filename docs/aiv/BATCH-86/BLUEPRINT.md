BATCH BLUEPRINT — BATCH-86
═══════════════════════════════════════════════════════════
Batch ID: BATCH-86 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-06 | Sequencing: SEQUENTIAL
───────────────────────────────────────────────────────────
GOAL: Filter search results by relevance to the original research domain.
Uses embedding similarity to score each paper against the domain query.
Papers below threshold are excluded before gap analysis.
───────────────────────────────────────────────────────────
SCOPE:
  MUST: RelevanceFilter scores papers via embedding cosine similarity
  MUST: Configurable threshold (default 0.3)
  MUST: Returns filtered list with scores
  MUST NOT: Remove all papers (guaranteed minimum if any exist)
───────────────────────────────────────────────────────────
HARD BOUNDARIES:
  HB-01: Must return at least 5 papers (if available)
  HB-02: Filter failure returns original list unchanged
───────────────────────────────────────────────────────────
TEST BASELINE: 2,042 | Delta: +8 | Expected: 2,050
───────────────────────────────────────────────────────────
TASK-01: RelevanceFilter (Critical)
  Files: backend/pipeline/literature/relevance_filter.py (NEW)
  Tests: 8 tests
───────────────────────────────────────────────────────────
BAC-01: RelevanceFilter scores and filters papers
BAC-02: Configurable threshold
BAC-03: Minimum paper guarantee
BAC-04: CHANGELOG.md updated
═══════════════════════════════════════════════════════════
