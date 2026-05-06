BATCH BLUEPRINT — BATCH-89
═══════════════════════════════════════════════════════════
Batch ID: BATCH-89 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-06 | Sequencing: SEQUENTIAL
───────────────────────────────────────────────────────────
GOAL: Create AntiFabricationGuard that checks proposals and ideas for
hallucinated citations, fabricated claims, and unverifiable statistics.
Adds confidence warnings to outputs.
───────────────────────────────────────────────────────────
TEST BASELINE: 2,063 | Delta: +10 | Expected: 2,073
───────────────────────────────────────────────────────────
TASK-01: AntiFabricationGuard (Critical)
  Files: backend/pipeline/safety/__init__.py (NEW),
         backend/pipeline/safety/anti_fabrication.py (NEW)
  Tests: 10 tests
───────────────────────────────────────────────────────────
BAC-01: Guard detects suspicious DOI patterns
BAC-02: Guard flags unverifiable statistics (e.g. "99.7% improvement")
BAC-03: Guard adds confidence warnings to proposals
BAC-04: CHANGELOG.md updated
HB-01: Guard MUST NOT reject all proposals (fail-open)
HB-02: Guard MUST NOT modify proposal content (only annotate)
═══════════════════════════════════════════════════════════
