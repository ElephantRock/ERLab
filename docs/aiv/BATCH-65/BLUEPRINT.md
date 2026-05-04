BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-65
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead (Ivory Wolf Session)
Date Issued:              2026-05-04
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Parallel

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Enable recombination of top ideas from different pipeline runs
by extracting structured "method DNA" and creating a recombination
API endpoint with traceability.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Extract structured method DNA from ideas (core technique, domain, evaluation)
  - Create POST /recombination/propose endpoint that takes 2+ run IDs
  - Use IdeaRecombinator from BATCH-62 to generate child ideas
  - Store recombined ideas with source_idea_ids traceability

What the code MUST NOT do:
  - Must not modify existing pipeline stages or orchestrator
  - Must not change existing API endpoints
  - Must not require frontend changes (API-only in this batch)

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Backend:  python -m ruff check backend/

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
HB-01: Recombination MUST fail gracefully if any run ID has <2 ideas
       (return 400 with clear error, not 500).
HB-02: No more than 10 recombined ideas may be generated per request.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
New file: backend/pipeline/generation/method_dna.py
  MethodDNA dataclass:
    - core_technique: str (e.g. "reinforcement learning", "causal inference")
    - domain: str (e.g. "healthcare", "NLP")
    - evaluation_approach: str
    - method_keywords: list[str]

New file: backend/api/routes/recombination.py
  POST /recombination/propose
  Body: {"run_ids": [1, 2], "max_ideas": 5}
  Response: {"recombined_ideas": [...], "method_dna": [...]}

Existing: IdeaRecombinator from backend/pipeline/generation/recombination.py

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
BATCH-62: IdeaRecombinator must exist (verified: yes)
BATCH-14: Idea model with source_gap_ids (verified: yes)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline: ~211 backend passing, 343 frontend passing
  Expected delta: +5 backend tests
  Expected total: ~216 backend, 343 frontend

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-65/TASK-01 — Method DNA Extraction
  Files: backend/pipeline/generation/method_dna.py (create),
         backend/tests/test_pipeline/test_method_dna.py (create)
  Tests: 3 unit tests
  AC-01-01: extract_dna(idea) returns MethodDNA with populated fields
  AC-01-02: Handles ideas with missing/empty fields gracefully
  AC-01-03: Keywords extracted from method text

TASK-02: BATCH-65/TASK-02 — Cross-Run Recombination API
  Files: backend/api/routes/recombination.py (create),
         backend/api/app.py (modify — register router),
         backend/tests/test_api/test_recombination.py (create)
  Tests: 2 integration tests
  AC-02-01: POST /recombination/propose returns recombined ideas
  AC-02-02: Returns 400 if run has <2 ideas (HB-01)
  AC-02-03: Caps at 10 ideas per request (HB-02)

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Method DNA extractable from any idea in DB
  BAC-02: Recombination API produces traceable child ideas
  BAC-03: CHANGELOG.md updated
  BAC-04: Documents archived under /docs/aiv/BATCH-65/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

Reviewer Report ID:       REVIEW-BATCH-65-2026-05-04
Review Cycle:             1
Lead Decision:            [x] ACCEPT
Zero flags — clean Blueprint.

Blueprint Version: 1.0
Lead Sign: Lead (Ivory Wolf) 2026-05-04 17:35

═══════════════════════════════════════════════════════════
