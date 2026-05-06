BATCH BLUEPRINT — BATCH-90 (REVISED)
═══════════════════════════════════════════════════════════
Batch ID: BATCH-90 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-06 | Sequencing: SEQUENTIAL
───────────────────────────────────────────────────────────
GOAL: Add sandboxed code executor for proposal feasibility validation.
Runs short code snippets (e.g. data loading checks) in an isolated
subprocess to verify feasibility claims.
───────────────────────────────────────────────────────────
TEST BASELINE: 2,073 | Delta: +8 | Expected: 2,081
───────────────────────────────────────────────────────────
TASK-01: SandboxExecutor (High)
  Files: backend/pipeline/sandboxing/executor.py (NEW)
  Tests: 8 tests
───────────────────────────────────────────────────────────
BAC-01: Execute short code snippets safely
BAC-02: Timeout enforced (default 5s)
BAC-03: Network isolated
BAC-04: CHANGELOG.md updated
HB-01: Untrusted code MUST NOT access filesystem outside /tmp
HB-02: Executor MUST NOT hang (> timeout kills process)
═══════════════════════════════════════════════════════════
