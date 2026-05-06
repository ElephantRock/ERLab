BATCH BLUEPRINT — BATCH-101
═══════════════════════════════════════════════════════════
Batch ID: BATCH-101 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-07
───────────────────────────────────────────────────────────
GOAL: Wire SoulLoader, JournalWriter, and ContextManager into
the PipelineOrchestrator so all LLM calls use research philosophy,
pipeline runs produce journals, and prompts respect token budgets.
───────────────────────────────────────────────────────────
TEST BASELINE: 2,152 | Delta: +12 | Expected: 2,164
───────────────────────────────────────────────────────────
TASK-01: SoulLoader integration (Critical)
  Wire inject_soul() into all system prompt construction.
  Tests: 4

TASK-02: JournalWriter integration (Critical)
  Wire JournalWriter into pipeline run lifecycle.
  Tests: 4

TASK-03: ContextManager integration (High)
  Wire ContextManager into stage prompt assembly.
  Tests: 4
───────────────────────────────────────────────────────────
BAC-01: SoulLoader prepends philosophy to all LLM prompts
BAC-02: JournalWriter generates notes.md + README.md per run
BAC-03: ContextManager manages token budgets for stage prompts
BAC-04: CHANGELOG.md updated
HB-01: SoulLoader failure MUST NOT crash pipeline
HB-02: JournalWriter failure MUST NOT crash pipeline
═══════════════════════════════════════════════════════════
