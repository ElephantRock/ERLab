BATCH BLUEPRINT — BATCH-105
═══════════════════════════════════════════════════════════
Batch ID: BATCH-105 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-07
───────────────────────────────────────────────────────────
GOAL: (1) Add max_time and max_cost params to pipeline runs.
Pipeline degrades gracefully when approaching limits.
(2) Domain-specific prompt templates for CS, bio, social science.
───────────────────────────────────────────────────────────
TEST BASELINE: 2,186 | Delta: +10 | Expected: 2,196
───────────────────────────────────────────────────────────
TASK-01: Budget/Time Controls (Critical)
  Files: backend/pipeline/budget_guard.py (NEW),
         backend/api/schemas.py (MODIFY)
  Tests: 6 tests

TASK-02: Domain Prompt Templates (High)
  Files: backend/pipeline/prompts/domains/ (NEW)
  Tests: 4 tests
───────────────────────────────────────────────────────────
BAC-01: max_time and max_cost in PipelineRunRequest
BAC-02: BudgetGuard degrades pipeline when approaching limits
BAC-03: Domain prompts enhance LLM output quality
BAC-04: CHANGELOG.md updated
HB-01: Budget guard MUST NOT crash pipeline — only degrade
═══════════════════════════════════════════════════════════
