BATCH BLUEPRINT — BATCH-91
═══════════════════════════════════════════════════════════
Batch ID: BATCH-91 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-07 | Sequencing: SEQUENTIAL
───────────────────────────────────────────────────────────
GOAL: 3-tier context management for LLM calls. System prompt (always),
domain context (papers + gaps), and task context (current stage).
Manages token budgets to avoid context overflow.
───────────────────────────────────────────────────────────
TEST BASELINE: 2,081 | Delta: +10 | Expected: 2,091
───────────────────────────────────────────────────────────
TASK-01: ContextManager (Critical)
  Files: backend/pipeline/context/__init__.py (NEW),
         backend/pipeline/context/manager.py (NEW)
  Tests: 10 tests
───────────────────────────────────────────────────────────
BAC-01: 3-tier context: system + domain + task
BAC-02: Token budget enforcement
BAC-03: Graceful truncation of long contexts
BAC-04: CHANGELOG.md updated
HB-01: MUST NOT exceed model max_tokens
HB-02: Truncation MUST preserve system prompt
═══════════════════════════════════════════════════════════
