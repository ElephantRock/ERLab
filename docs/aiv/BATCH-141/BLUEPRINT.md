BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-141
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-10
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Parallel (all 3 tasks are independent)

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────

Fix the three highest-impact-to-effort defects identified across the
Technical Architecture Audit, UX Audit, and E2E QA Audit:

1. Change the pipeline strategy default from "deep_research" (25 min) to
   "fast_scan" (3 min) — reducing first-time-user wait by 22 minutes.
2. Wire the "Resume Pipeline" button on the run-detail page to actually
   call the backend resume endpoint — eliminating a dead-action button.
3. Fix the `usePipelineProgress` hook's idea-fetching logic to use the
   current runId instead of `listRuns({limit:1})` — preventing a race
   condition that could display ideas from the wrong run.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────

What the code MUST do:
  - Default strategy selector to "fast_scan" when the pipeline-new page
    loads (and when arriving from the onboarding overlay with a topic)
  - Show strategy descriptions and time estimates that match the actual
    strategy names in the backend registry
  - Resume button on `/runs/:id` must call `POST /api/v1/pipeline/runs/{id}/resume`
    (or equivalent) and update the UI to show the run as "running" again
  - After pipeline completion, ideas must be fetched using the current
    `runId` (not a global "latest run" query)

What the code MUST NOT do:
  - Must NOT change any backend code (frontend-only batch)
  - Must NOT change the strategy registry or preset definitions
  - Must NOT alter the onboarding overlay logic itself (that's BATCH-147)
  - Must NOT add new API endpoints

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────

  Lint command:  cd frontend && npx tsc --noEmit 2>&1 | tail -5

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────

  HB-01: The pipeline strategy selector MUST default to "fast_scan" on
         every fresh page load of /pipeline/new. This MUST be verifiable
         by inspecting the initial useState value for the strategy state
         variable in run-config-form.tsx.

  HB-02: The Resume button on /runs/:id MUST call a backend API endpoint
         (not just navigate or show a toast). The button click MUST
         trigger an HTTP request. If the API call fails, an error toast
         MUST be shown to the user.

  HB-03: The idea-fetching logic after pipeline completion in
         pipeline-new.tsx MUST use the current `runId` state variable
         to fetch ideas (via getRunIdeas(runId)), not via listRuns({limit:1}).
         There MUST be no call to listRuns inside the fetchIdeas function.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────

Frontend types (from frontend/src/api/types.ts):

  PipelineRunRequest.strategy: string | undefined
    - Values matching backend: "fast_scan", "deep_research",
      "academic_proposal", "literature_review"

  TriggerRunResponse: { run_id: string; status: string }

  PipelineRunDetail:
    .id: number
    .status: "pending" | "running" | "completed" | "failed"
    .stages_completed: string[]
    .current_stage: string | null

  IdeaSummary:
    .id: number
    .title: string
    .domain: string
    .overall_score: number | null

Backend API endpoints (from backend/api/routes/pipeline.py):

  POST /api/v1/pipeline/runs → TriggerRunResponse
  GET  /api/v1/pipeline/runs/{id} → PipelineRunDetail
  GET  /api/v1/pipeline/runs/{id}/ideas → { ideas: IdeaSummary[] }
  POST /api/v1/pipeline/resume/{run_id} → { status, run_id, ideas_count, gaps_count, proposals_count }
    NOTE: run_id is a string (UUID-style), not numeric. Endpoint path is
    /resume/{run_id}, NOT /runs/{id}/resume. Verified in pipeline.py:223.

Frontend API functions (from frontend/src/api/pipeline.ts):

  triggerRun(req: PipelineRunRequest): Promise<TriggerRunResponse>
  getRunDetail(id: number): Promise<PipelineRunDetail>
  getRunIdeas(id: number): Promise<{ ideas: IdeaSummary[] }>
  resumeRun(runId: string): Promise<{ status: string; run_id: string; ideas_count: number; gaps_count: number; proposals_count: number }>  ← MUST ADD
  listRuns(params): Promise<{ runs: PipelineRunSummary[]; total: number }>
  cancelRun(id: string): Promise<{ status: string }>

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────

  AUTH-01: The strategy selector value is the single source of truth for
           which strategy the backend receives. No other code path may
           override it after user selection.

  AUTH-02: The runId state variable in pipeline-new.tsx is the single
           source of truth for which run's ideas to display after
           completion. No heuristic ("latest run") may substitute.

  AUTH-03: The Resume button must handle three states:
           (a) API call succeeds → navigate to /runs/{id} with running state
           (b) API call fails with 4xx/5xx → show error toast
           (c) API call fails with network error → show error toast

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────

  BATCH-140: EROCK_ENV toggle — ACTIVE, no conflicts
  BATCH-137: .env.untracked — ACTIVE, no conflicts
  Backend resume endpoint: Must exist at POST /api/v1/pipeline/resume/{run_id}
    (Verified: pipeline.py:223, mounted at /api/v1/pipeline per app.py:151)

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────

  State file exists:       [x] YES
  Last Updated:            2026-05-10
  Batches since update:    0 (BATCH-140 was the last update)
  Reconciliation audit:    [x] N/A (< 5 batches since update)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────

  Baseline at Blueprint issuance:  2,480 existing tests
  Expected delta (all Tasks):      +18 new tests
  Expected total at Batch close:   2,498

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-141/TASK-01 — Strategy Default Change
  Priority:          Critical
  Description:       Change the pipeline strategy selector's default value
                     from "deep_research" to "fast_scan" in the run-config-form
                     component. Update any related test files that assert the
                     old default. Verify the strategy description text and
                     time estimates still display correctly for all 4 strategies.
  Files in scope:
    - frontend/src/components/pipeline/run-config-form.tsx
    - frontend/src/pages/__tests__/pipeline-results.test.tsx (if it asserts defaults)
  Depends on:        None
  Required Tests:
    | Test ID          | Type      | Behavior Verified                                   | Failure Mode                                     | Falsified By                                           | Pass Criteria                                        |
    |:-----------------|:----------|:----------------------------------------------------|:-------------------------------------------------|:-------------------------------------------------------|:-----------------------------------------------------|
    | TEST-141-01-01   | unit      | Default strategy state is "fast_scan" on mount       | Component renders with "deep_research" selected  | Change useState back to "deep_research"                | render().find('select[data-testid="strategy-select"]').value === "fast_scan" |
    | TEST-141-01-02   | unit      | Strategy select has 4 options with correct values    | Options are missing or have wrong values          | Remove one option from the select                      | All 4 options present: fast_scan, deep_research, academic_proposal, literature_review |
    | TEST-141-01-03   | unit      | fast_scan option shows "~2-5 min" time estimate      | Description text is missing or shows wrong time   | Change the description text to empty string           | fast_scan description contains "2-5 min" or "~3 min"  |
    | TEST-141-01-04   | unit      | deep_research option shows "~25 min" time estimate   | Description text is missing                       | Change the description text to empty string           | deep_research description contains "25 min"           |
    | TEST-141-01-05   | integration | Submitted config includes strategy="fast_scan" by default | Form submits "deep_research" when user clicks Start | Change default back to "deep_research"               | onSubmit callback receives { strategy: "fast_scan", ... } |
    | TEST-141-01-06   | unit      | Changing strategy updates the description text       | Description stays on fast_scan text after changing to deep_research | Remove the onChange handler                      | After selecting "deep_research", description contains "Full pipeline" |
  Acceptance Criteria:
    AC-01-01: The strategy select defaults to "fast_scan" on page load.
    AC-01-02: All 4 strategy options render with correct values and time estimates.
    AC-01-03: The form submission includes the selected strategy value.
  Traceability:
    AC-01-01 → TEST-141-01-01
    AC-01-02 → TEST-141-01-02, TEST-141-01-03, TEST-141-01-04
    AC-01-03 → TEST-141-01-05, TEST-141-01-06


TASK-02: BATCH-141/TASK-02 — Resume Button Wiring
  Priority:          Critical
  Description:       Wire the "Resume Pipeline" button on the run-detail page
                     to call the backend resume endpoint. Add a `resumeRun`
                     function to the frontend API client if it doesn't exist.
                     Handle loading, success, and error states with proper UI
                     feedback (spinner while loading, navigate on success, toast
                     on error).
  Files in scope:
    - frontend/src/api/pipeline.ts (add resumeRun if missing)
    - frontend/src/pages/run-detail.tsx
  Depends on:        None
  Required Tests:
    | Test ID          | Type      | Behavior Verified                                   | Failure Mode                                     | Falsified By                                           | Pass Criteria                                        |
    |:-----------------|:----------|:----------------------------------------------------|:-------------------------------------------------|:-------------------------------------------------------|:-----------------------------------------------------|
    | TEST-141-02-01   | unit      | resumeRun function calls correct API endpoint        | Function calls wrong endpoint or no endpoint     | Change the URL path to /wrong-endpoint                | resumeRun("run_123") calls POST /api/v1/pipeline/resume/run_123 |
    | TEST-141-02-01b  | unit      | Resume button is NOT visible when status is not "failed" | Button appears for completed/running runs | Remove the conditional status check | Button absent when run.status === "completed" AND "running" |
    | TEST-141-02-02   | unit      | Resume button is visible when run status is "failed" | Button is hidden or not rendered for failed runs  | Add condition `status !== "failed"` to render check    | Button present in DOM when run.status === "failed"    |
    | TEST-141-02-03   | unit      | Resume button triggers API call on click             | Clicking button does nothing (no handler)         | Remove the onClick handler                             | Click triggers resumeRun(runId) call                  |
    | TEST-141-02-04   | unit      | Loading state shown during resume API call           | Button stays in default state during API call     | Remove the isPending state check                       | Button shows "Resuming..." or Loader2 while pending   |
    | TEST-141-02-05   | integration | Error toast shown when resume API fails            | Error is silently swallowed, no user feedback     | Remove the onError callback from useMutation           | toast.error() called with error message on API failure |
    | TEST-141-02-06   | integration | Success navigates to run detail with fresh data    | User stays on stale page after successful resume  | Remove the navigate() call from onSuccess              | navigate(/runs/${id}) called on successful resume     |
  Acceptance Criteria:
    AC-02-01: The Resume button is visible only when run status is "failed".
    AC-02-02: Clicking Resume calls the backend resume API endpoint.
    AC-02-03: Loading state is displayed during the API call.
    AC-02-04: On success, the page refreshes or navigates to show the running pipeline.
    AC-02-05: On error, a toast notification displays the error message.
  Traceability:
    AC-02-01 → TEST-141-02-02, TEST-141-02-01b
    AC-02-02 → TEST-141-02-01, TEST-141-02-03
    AC-02-03 → TEST-141-02-04
    AC-02-04 → TEST-141-02-06
    AC-02-05 → TEST-141-02-05


TASK-03: BATCH-141/TASK-03 — Idea Fetch Race Condition Fix
  Priority:          High
  Description:       Fix the `fetchIdeas` function in pipeline-new.tsx to
                     fetch ideas using the current `runId` state variable
                     instead of calling `listRuns({limit:1})` which returns
                     the globally latest run (not necessarily the current one).
                     Replace the two-step "find latest run, then get ideas"
                     pattern with a direct `getRunIdeas(runId)` call.
  Files in scope:
    - frontend/src/pages/pipeline-new.tsx
  Depends on:        None
  Required Tests:
    | Test ID          | Type      | Behavior Verified                                   | Failure Mode                                     | Falsified By                                           | Pass Criteria                                        |
    |:-----------------|:----------|:----------------------------------------------------|:-------------------------------------------------|:-------------------------------------------------------|:-----------------------------------------------------|
    | TEST-141-03-01   | unit      | fetchIdeas calls getRunIdeas(runId) directly         | Function still calls listRuns({limit:1})          | Revert to the old listRuns-based implementation        | getRunIdeas.mockCalledWith(runId) returns true         |
    | TEST-141-03-02   | unit      | fetchIdeas does NOT call listRuns                    | Race condition still exists via listRuns call     | Add listRuns back into fetchIdeas                      | listRuns is not called inside fetchIdeas               |
    | TEST-141-03-03   | integration | Ideas from the correct runId are displayed         | Ideas from a different run are shown              | Mock getRunIdeas to return ideas for a different ID    | Displayed ideas match getRunIdeas(runId) response      |
    | TEST-141-03-04   | unit      | Error state set when getRunIdeas fails               | Error swallowed, user sees stale "Loading..."     | Remove the catch block that sets setIdeasError         | setIdeasError called with error message               |
    | TEST-141-03-05   | unit      | Ideas state set to empty array on fetch failure      | Old ideas from previous run persist               | Remove the setIdeas([]) call from catch block          | ideas.length === 0 after failed fetch                 |
    | TEST-141-03-06   | unit      | fetchIdeas is only called when isComplete is true     | Ideas fetched before pipeline completes           | Move the fetchIdeas call outside the isComplete guard   | getRunIdeas not called when isComplete === false       |
  Acceptance Criteria:
    AC-03-01: fetchIdeas uses getRunIdeas(runId) directly, not listRuns.
    AC-03-02: No call to listRuns exists inside the fetchIdeas function.
    AC-03-03: Ideas displayed match the current runId, not a "latest run" heuristic.
    AC-03-04: Error state is properly set on fetch failure.
  Traceability:
    AC-03-01 → TEST-141-03-01
    AC-03-02 → TEST-141-03-02
    AC-03-03 → TEST-141-03-03
    AC-03-04 → TEST-141-03-04, TEST-141-03-05

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────

  BAC-01: A first-time user arriving at /pipeline/new sees "Quick Scan (~2-5 min)"
          as the default strategy, not "Deep Research (~25 min)".
  BAC-02: A user on /runs/:id with a failed run can click "Resume Pipeline" and
          the pipeline actually resumes (API call + UI update).
  BAC-03: CHANGELOG.md updated with BATCH-141 entry.
  BAC-04: All documents archived under /docs/aiv/BATCH-141/.

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

Reviewer Report ID:       REV-141-01
Review Cycle:             1
Lead Decision:            [x] ACCEPT WITH MODIFICATIONS

Flags acted on:
  CHK-13 → Action taken: Added TEST-141-02-01b — negative test verifying Resume
           button is hidden when status is not "failed". Updated AC-02-01 traceability
           to include both positive (TEST-141-02-02) and negative (TEST-141-02-01b) tests.
  CHK-19 → Action taken: Corrected resume endpoint path throughout Data Models,
           Dependency Map, and AUTH-03. Changed from
           `POST /api/v1/pipeline/runs/{id}/resume` (wrong) to
           `POST /api/v1/pipeline/resume/{run_id}` (correct, verified pipeline.py:223).
           Changed run_id type from numeric to string.
  CHK-23 → Action taken: Updated TEST-141-02-01 pass criteria to reflect the correct
           endpoint: `resumeRun("run_123") calls POST /api/v1/pipeline/resume/run_123`.
           Changed parameter from numeric 42 to string "run_123" to match actual type.

Blueprint Version after response: 1.1
Lead Sign:                ivory-wolf — 2026-05-10T03:02:00+03:00

═══════════════════════════════════════════════════════════
