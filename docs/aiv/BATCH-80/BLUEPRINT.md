BATCH BLUEPRINT — BATCH-80
═══════════════════════════════════════════════════════════
Batch ID: BATCH-80 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-06 | Sequencing: SEQUENTIAL
───────────────────────────────────────────────────────────
GOAL: Add iterative reflection after gap analysis and ideation.
LLM evaluates its own output; if score < threshold, regenerate with feedback.
───────────────────────────────────────────────────────────
SCOPE:
  MUST: After gap_analysis, LLM evaluates gap coverage
  MUST: After ideation, LLM evaluates idea novelty
  MUST: If score < threshold, regenerate with feedback (max 3 iterations)
  MUST NOT: Make reflection mandatory for fast_scan
  MUST NOT: Change gap or idea data models
───────────────────────────────────────────────────────────
HARD BOUNDARIES:
  HB-01: Max 3 iterations — MUST NOT loop infinitely
  HB-02: Reflection disabled for fast_scan
  HB-03: Each iteration logged with input/output score
───────────────────────────────────────────────────────────
LINT: python -m ruff check backend/ && python -m pytest --co -q
───────────────────────────────────────────────────────────
STATE.md: Updated BATCH-79 | 0 batches since
───────────────────────────────────────────────────────────
TEST BASELINE: 1,972 | Delta: +12 | Expected: 1,984
───────────────────────────────────────────────────────────
TASK-01: ReflectionStage Implementation (Critical)
  Files: backend/pipeline/reflection/__init__.py (NEW),
         backend/pipeline/reflection/reflector.py (NEW),
         backend/pipeline/reflection/prompts/gap_reflection.md (NEW),
         backend/pipeline/reflection/prompts/idea_reflection.md (NEW)
  Tests: 8 tests

TASK-02: Orchestrator Integration (High)
  Files: backend/pipeline/orchestrator.py (MODIFY),
         backend/pipeline/strategies/presets.py (MODIFY)
  Tests: 5 tests
───────────────────────────────────────────────────────────
BAC-01: Reflection improves gap/idea quality (measured by score)
BAC-02: fast_scan not affected
BAC-03: Iterations capped and logged
BAC-04: CHANGELOG.md updated
BAC-05: All docs under /docs/aiv/BATCH-80/
═══════════════════════════════════════════════════════════
