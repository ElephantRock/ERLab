BATCH BLUEPRINT — BATCH-84
═══════════════════════════════════════════════════════════
Batch ID: BATCH-84 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-06 | Sequencing: SEQUENTIAL
───────────────────────────────────────────────────────────
GOAL: Every pipeline run produces a research journal with notes.md
(stage-by-stage notes) and README.md (clean summary). Files are
downloadable from the UI.
───────────────────────────────────────────────────────────
SCOPE:
  MUST: JournalWriter accumulates notes during execution
  MUST: Generates notes.md (detailed) and README.md (summary)
  MUST: Journal accessible via API endpoint
  MUST NOT: Expose internal prompts or API keys
───────────────────────────────────────────────────────────
HARD BOUNDARIES:
  HB-01: Journal MUST NOT contain API keys or raw prompts
  HB-02: Journal generation MUST NOT slow down pipeline
  HB-03: Journal files persist in data/runs/{run_id}/
───────────────────────────────────────────────────────────
LINT: python -m ruff check backend/ && python -m pytest --co -q
───────────────────────────────────────────────────────────
STATE.md: Updated BATCH-83 | 0 batches since
───────────────────────────────────────────────────────────
TEST BASELINE: 2,020 | Delta: +8 | Expected: 2,028
───────────────────────────────────────────────────────────
TASK-01: JournalWriter (Critical)
  Files: backend/pipeline/journal/__init__.py (NEW),
         backend/pipeline/journal/writer.py (NEW)
  Tests: 6 tests

TASK-02: API Endpoint + Integration (High)
  Files: backend/api/routes/pipeline.py (MODIFY)
  Tests: 2 tests
───────────────────────────────────────────────────────────
BAC-01: Journal files generated per pipeline run
BAC-02: Journal accessible via API
BAC-03: No sensitive data in journal
BAC-04: CHANGELOG.md updated
BAC-05: All docs under /docs/aiv/BATCH-84/
═══════════════════════════════════════════════════════════
