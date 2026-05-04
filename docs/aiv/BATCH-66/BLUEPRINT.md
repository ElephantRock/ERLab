BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-66
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead (Ivory Wolf Session)
Date Issued:              2026-05-04
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential (TASK-02 depends on TASK-01, TASK-03 depends on TASK-02)

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Enable the platform to generate Python experiment code from ideas,
execute it in the existing sandbox, capture results, and feed them
back into idea scoring.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Generate experiment code from an idea's method and evaluation approach
  - Execute generated code in the existing SandboxManager (Docker/Subprocess/Noop)
  - Store experiment results in a new DB table
  - Add experiment results to the idea detail API response

What the code MUST NOT do:
  - Must not modify existing SandboxManager code
  - Must not allow arbitrary code execution without SecurityValidator check
  - Must not block the pipeline — experiments run on-demand, not in the pipeline

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Backend:  python -m ruff check backend/

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
HB-01: All experiment code MUST pass SecurityValidator before execution.
       No bypass allowed.
HB-02: Experiment execution MUST timeout after 30 seconds (configurable).
       No infinite loops.
HB-03: Experiments run on-demand via API, NOT automatically during pipeline runs.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
New table: experiment_results
  - id: INTEGER PK
  - idea_id: INTEGER FK → ideas.id
  - code_md: TEXT (the generated experiment code)
  - stdout: TEXT
  - stderr: TEXT
  - exit_code: INTEGER
  - success: BOOLEAN
  - execution_time_seconds: FLOAT
  - error: TEXT (nullable)
  - created_at: DATETIME

New file: backend/pipeline/experiment/experiment_generator.py
  - ExperimentGenerator class
  - generate(idea) → str (Python code)

Existing: backend/pipeline/experiment/runner.py (ExperimentRunner)
Existing: backend/pipeline/experiment/validator.py (SecurityValidator)
Existing: backend/pipeline/sandboxing/manager.py (SandboxManager)

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
BATCH-49: ExperimentRunner + SecurityValidator (verified: yes)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline: 228 backend passing, 343 frontend passing
  Expected delta: +8 backend tests
  Expected total: ~236 backend, 343 frontend

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-66/TASK-01 — Experiment Code Generator
  Files: backend/pipeline/experiment/experiment_generator.py (create ~200 lines),
         backend/tests/test_pipeline/test_experiment_generator.py (create)
  Tests: 3 unit tests
  AC-01-01: generate(idea) returns valid Python code string
  AC-01-02: Generated code includes hypothesis test, baseline comparison
  AC-01-03: Code uses standard libraries only (no pip install required)

TASK-02: BATCH-66/TASK-02 — Experiment Results DB Table + Storage
  Files: backend/db/models.py (modify — add ExperimentResult model),
         backend/db/crud.py (modify — add save_experiment_result),
         backend/pipeline/experiment/models.py (verify/modify if needed),
         backend/tests/test_db/test_experiment_results.py (create)
  Depends on: TASK-01
  Tests: 2 unit tests
  AC-02-01: ExperimentResult model saves to DB
  AC-02-02: Results queryable by idea_id

TASK-03: BATCH-66/TASK-03 — Experiment API Endpoint + Scoring Boost
  Files: backend/api/routes/experiments.py (modify — add POST /ideas/{id}/run-experiment),
         backend/api/routes/ideas.py (modify — include experiment results in response),
         backend/tests/test_api/test_experiment_api.py (create)
  Depends on: TASK-02
  Tests: 3 integration tests
  AC-03-01: POST /ideas/{id}/run-experiment generates code, validates, executes, stores
  AC-03-02: GET /ideas/{id} includes experiment_results when present
  AC-03-03: SecurityValidator blocks unsafe code (HB-01)

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Full experiment lifecycle: idea → code → validate → execute → store
  BAC-02: Results visible in API
  BAC-03: CHANGELOG.md updated
  BAC-04: Documents archived under /docs/aiv/BATCH-66/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

Reviewer Report ID:       REVIEW-BATCH-66-2026-05-04
Review Cycle:             1
Lead Decision:            [x] ACCEPT
Zero flags.

Blueprint Version: 1.0
Lead Sign: Lead (Ivory Wolf) 2026-05-04

═══════════════════════════════════════════════════════════
