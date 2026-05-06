BATCH BLUEPRINT — BATCH-87
═══════════════════════════════════════════════════════════
Batch ID: BATCH-87 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-06 | Sequencing: SEQUENTIAL
───────────────────────────────────────────────────────────
GOAL: Create SKILL.md defining the platform's capabilities and
constraints as a machine-readable manifest. Also add a recursive
search depth config to the literature search service.
───────────────────────────────────────────────────────────
TEST BASELINE: 2,050 | Delta: +6 | Expected: 2,056
───────────────────────────────────────────────────────────
TASK-01: SKILL.md Platform Manifest (High)
  Files: SKILL.md (NEW)
  Tests: 3 tests

TASK-02: Recursive Search Depth (High)
  Files: backend/pipeline/literature/search_service.py (MODIFY)
  Tests: 3 tests
───────────────────────────────────────────────────────────
BAC-01: SKILL.md exists and is valid YAML+Markdown
BAC-02: Recursive search config in Settings
BAC-03: CHANGELOG.md updated
═══════════════════════════════════════════════════════════
