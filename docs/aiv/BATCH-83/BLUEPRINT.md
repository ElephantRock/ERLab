BATCH BLUEPRINT — BATCH-83
═══════════════════════════════════════════════════════════
Batch ID: BATCH-83 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-06 | Sequencing: SEQUENTIAL
───────────────────────────────────────────────────────────
GOAL: (1) Create SOUL.md defining Elephant Rock's research philosophy.
(2) Create ErrorKnowledgeStore that logs rejection reasons and low scores
    for future runs to learn from.
───────────────────────────────────────────────────────────
SCOPE:
  MUST: SOUL.md is human-readable markdown defining research values
  MUST: SoulLoader injects philosophy into LLM prompts
  MUST: ErrorKnowledgeStore logs stage, input_hash, reason, suggestion
  MUST NOT: SOUL.md execute arbitrary code
  MUST NOT: ErrorKnowledgeStore modify past run data
───────────────────────────────────────────────────────────
HARD BOUNDARIES:
  HB-01: SOUL.md is declarative markdown only — no code execution
  HB-02: ErrorKnowledgeStore is append-only — no deletions
  HB-03: SoulLoader failure MUST NOT crash pipeline
───────────────────────────────────────────────────────────
LINT: python -m ruff check backend/ && python -m pytest --co -q
───────────────────────────────────────────────────────────
STATE.md: Updated BATCH-82 | 0 batches since
───────────────────────────────────────────────────────────
TEST BASELINE: 2,010 | Delta: +10 | Expected: 2,020
───────────────────────────────────────────────────────────
TASK-01: SOUL.md + SoulLoader (Critical)
  Files: SOUL.md (NEW), backend/pipeline/soul_loader.py (NEW)
  Tests: 5 tests

TASK-02: ErrorKnowledgeStore (High)
  Files: backend/pipeline/knowledge/error_store.py (NEW)
  Tests: 5 tests
───────────────────────────────────────────────────────────
BAC-01: SOUL.md defines research philosophy
BAC-02: SoulLoader injects into prompts
BAC-03: ErrorKnowledgeStore logs failures
BAC-04: CHANGELOG.md updated
BAC-05: All docs under /docs/aiv/BATCH-83/
═══════════════════════════════════════════════════════════
