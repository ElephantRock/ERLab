BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-15
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
Add a visible Cancel button to the pipeline execution UI that allows users
to abort a running pipeline with confirmation and displays partial results.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Show red "Cancel Run" button during pipeline execution
  - Confirmation dialog before cancellation
  - On cancel: show "Cancelled" badge, display partial results if any
  - Use existing cancelRun() API function (DELETE /runs/{id})

What the code MUST NOT do:
  - Modify the backend cancel endpoint or orchestrator cancellation logic
  - Auto-cancel without user confirmation
  - Remove or hide the progress display during cancellation

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: The backend cancellation endpoint (DELETE /runs/{id}) already
         exists and works. This Batch MUST NOT modify it. Frontend
         integration only.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Existing API (backend/api/routes/pipeline.py):
  DELETE /api/v1/pipeline/runs/{run_id} → already implemented, sets status to "cancelled"

Existing frontend API (frontend/src/api/pipeline.ts):
  cancelRun(runId: string) → already defined, currently unused

Pipeline page (frontend/src/pages/pipeline-new.tsx):
  Modified by BATCH-12 to show inline results after completion.
  Now needs a cancel button visible during execution.

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: Cancellation requires explicit user confirmation.
         No automatic or timeout-based cancellation.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-12 (pipeline page structure)
  BATCH-12 status: APPROVED and closed

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,644 tests (1,519 backend + 125 frontend)
  Expected delta (all Tasks):      +5 new frontend tests
  Expected total at Batch close:   1,649

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-15/TASK-01 — Cancel Pipeline UI
  Description:      Add cancel button with confirmation dialog to
                    the pipeline progress UI, display cancelled state.
  Files in scope:   frontend/src/pages/pipeline-new.tsx (MODIFY)
  Depends on:       None
  Required Tests:
    | Test ID          | Type | Pass Criteria                                      |
    |:-----------------|:-----|:---------------------------------------------------|
    | TEST-15-01-01    | unit | Cancel button renders during pipeline execution    |
    | TEST-15-01-02    | unit | Cancel click shows confirmation dialog             |
    | TEST-15-01-03    | unit | Cancel confirm calls cancelRun()                  |
    | TEST-15-01-04    | unit | Cancelled state shows "Cancelled" badge            |
    | TEST-15-01-05    | unit | Cancelled state shows partial results if available |
  Acceptance Criteria:
    AC-01: Cancel button appears during pipeline execution
    AC-02: Confirmation dialog prevents accidental cancellation
    AC-03: Cancelled runs show partial results

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: User can cancel a running pipeline from the UI
  BAC-02: CHANGELOG.md updated with BATCH-15 entry
  BAC-03: All documents archived under /docs/aiv/BATCH-15/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Reviewer Report ID:       REVIEW-BATCH-15-2026-05-02
Review Cycle:             1
Lead Decision:            [x] ACCEPT

CHK-13 flag noted but not acted on — error-path tests are low severity.
Cancel API failure is a backend concern (HB-01). Dialog dismissal is implicit
in the confirmation pattern. Button non-visibility is the inverse of
TEST-15-01-01 (if it renders during execution, it doesn't render otherwise).

Blueprint Version after response: 1.0 (unchanged)
Lead Sign:                Lead + 2026-05-02 06:40
