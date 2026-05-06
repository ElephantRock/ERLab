BATCH BLUEPRINT — BATCH-78
═══════════════════════════════════════════════════════════
Batch ID: BATCH-78 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-06 | Sequencing: SEQUENTIAL
───────────────────────────────────────────────────────────
GOAL: Split LLM usage into thinking model (classification/extraction)
and generation model (proposal writing/idea generation).
───────────────────────────────────────────────────────────
SCOPE:
  MUST: Add thinking_model/generation_model config fields
  MUST: ProviderFactory resolves correct provider based on task type
  MUST: Default both to same model (backward compatible)
  MUST NOT: Change any stage's prompt or output format
  MUST NOT: Require two different API keys
───────────────────────────────────────────────────────────
HARD BOUNDARIES:
  HB-01: Default config (no model split) produces identical results to pre-BATCH-78
  HB-02: If thinking_model unavailable, fallback to generation_model
  HB-03: Model selection logged in pipeline traces
───────────────────────────────────────────────────────────
LINT: python -m ruff check backend/ && python -m pytest --co -q
───────────────────────────────────────────────────────────
STATE.md: Updated BATCH-77 | 0 batches since | N/A audit
───────────────────────────────────────────────────────────
TEST BASELINE: 1,945 | Delta: +15 | Expected: 1,960
───────────────────────────────────────────────────────────
TASK-01: BATCH-78/TASK-01 — Config + Provider Split (Critical)
  Files: backend/config.py (MODIFY), backend/providers/provider_factory.py (MODIFY)
  Tests: 8 tests (thinking/generation provider, fallback, defaults)

TASK-02: BATCH-78/TASK-02 — Model Selector (High)
  Files: backend/pipeline/model_selection.py (NEW)
  Tests: 7 tests (task type mapping, stage integration)
───────────────────────────────────────────────────────────
BAC-01: Model split configurable and backward-compatible
BAC-02: Classification uses thinking, generation uses generation model
BAC-03: CHANGELOG.md updated
BAC-04: All docs under /docs/aiv/BATCH-78/
═══════════════════════════════════════════════════════════
