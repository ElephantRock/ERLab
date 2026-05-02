BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-08
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead
Date Issued:              2026-05-02
Review SLA:               30 minutes
Execution SLA per Task:   60 minutes
Partial Sign-Off SLA:     15 minutes
Task Sequencing:          SEQUENTIAL (single task)

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Deliver an `erock dev` CLI command that starts both the backend (uvicorn)
and frontend (npm run dev) in a single terminal with colored log prefixes
and clean Ctrl+C shutdown.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Start uvicorn backend on port 8000 as a subprocess
  - Start npm frontend dev server on port 3000 as a subprocess
  - Stream both stdout/stderr to terminal with [BACKEND] / [FRONTEND] prefixes
  - Print both URLs after startup
  - Clean up both processes on Ctrl+C (SIGINT)
  - Detect if ports are already in use and report clearly

What the code MUST NOT do:
  - Install dependencies or check for node_modules existence
  - Require more than one terminal window
  - Modify any file other than the two declared in scope

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: The modification to backend/cli/main.py MUST NOT exceed 3 lines
         added (import + registration + blank line). No other changes
         to that file are permitted.

  HB-02: The command MUST NOT start if either port 8000 or 3000 is already
         in use. It must detect and report the conflict, then exit.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Current CLI registration (backend/cli/main.py):
  Uses Typer app with app.command() decorators.
  BATCH-07 added setup_wizard registration at line ~676.
  New registration follows the same pattern.

Backend start command:
  uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --reload

Frontend start command:
  npm run dev (in frontend/ directory, uses Vite, defaults to port 3000)

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: Process cleanup is the command's responsibility. Both child
         processes MUST be terminated before the command exits, regardless
         of exit reason (normal, SIGINT, error).

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  None — this Batch has no dependency on prior Batches.

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,365 existing tests
  Expected delta (all Tasks):      +5 new tests
  Expected total at Batch close:   1,370

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-08/TASK-01 — Dev Server Command
  Description:      Create `erock dev` CLI command that launches both
                    servers as managed subprocesses with unified output,
                    port conflict detection, and graceful shutdown.
  Files in scope:   backend/cli/commands/dev.py (NEW)
                    backend/cli/main.py (MODIFY — add import + command registration)
  Depends on:       None
  Required Tests:
    | Test ID          | Type     | Pass Criteria                                      |
    |:-----------------|:---------|:---------------------------------------------------|
    | TEST-08-01-01    | unit     | Command constructs correct uvicorn subprocess args  |
    | TEST-08-01-02    | unit     | Command constructs correct npm subprocess args      |
    | TEST-08-01-03    | unit     | SIGINT handler terminates both child processes      |
    | TEST-08-01-04    | unit     | Port-in-use detected and error reported             |
    | TEST-08-01-05    | e2e      | Both servers start and respond to health check      |
  Acceptance Criteria:
    AC-01: `erock dev` starts both servers and prints URLs
    AC-02: Ctrl+C kills both processes within 3 seconds
    AC-03: Port conflicts produce actionable error messages

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: `erock dev` starts backend + frontend in a single terminal
  BAC-02: CHANGELOG.md updated with BATCH-08 entry
  BAC-03: All documents archived under /docs/aiv/BATCH-08/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:       REVIEW-BATCH-08-2026-05-02
Review Cycle:             1
Lead Decision:            [x] ACCEPT

Reviewer flags noted but not acted on:
  CHK-13 (TEST SUFFICIENCY): Log prefix and URL printing are cosmetic output.
  The e2e test verifies both servers respond, which is the functional core.
  No modification required.

Blueprint Version after response: 1.0 (unchanged)
Lead Sign:                Lead + 2026-05-02 02:00

═══════════════════════════════════════════════════════════
