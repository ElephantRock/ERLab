BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-61
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead (Ivory Wolf Session)
Date Issued:              2026-05-04
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential (TASK-02 depends on TASK-01)

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Ensure every pipeline run completes end-to-end by adding
per-proposal timeout with graceful continuation, and stage-level
persistence so partially-completed runs can be resumed.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Wrap each proposal synthesis call in asyncio.wait_for() with a configurable
    per-proposal timeout (default 120s); on timeout, log and continue to next
  - Save ideas and gaps to the database immediately after their generation stages
    complete, before proposal synthesis begins
  - Add a --resume RUN_ID flag to the CLI that skips already-completed stages

What the code MUST NOT do:
  - Must not change the proposal synthesis logic itself (only add timeout wrapper)
  - Must not modify any pipeline stage internals
  - Must not change the API response schemas

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Backend:  python -m ruff check backend/
  Frontend: npx tsc --noEmit

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
HB-01: Per-proposal timeout MUST NOT exceed 300 seconds per proposal.
HB-02: The resume feature MUST verify stage completion by checking the
       pipeline_runs.current_stage field in the database, not by file existence.
HB-03: No existing API endpoint contract may change (response shapes preserved).

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
pipeline_runs table (existing):
  - current_stage: VARCHAR — tracks last completed stage name
  - status: VARCHAR — "running", "completed", "failed"

Stages in order:
  "literature_search" → "gap_analysis" → "idea_generation" →
  "novelty_checking" → "feasibility_scoring" → "proposal_synthesis" → "export"

Files:
  - backend/pipeline/orchestrator.py — PipelineOrchestrator.run()
  - backend/pipeline/synthesis/proposal_synthesizer.py — ProposalSynthesizer.synthesize()
  - backend/pipeline/persistence.py — advance_stage(), save_checkpoint()
  - backend/cli/main.py — CLI entry point with argparse

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
- The orchestrator is authoritative for stage ordering and completion tracking
- The CLI --resume flag reads stage state from the DB (persistence module)
- Per-proposal timeout uses config: stage_retry_max_delay (capped at 300s)

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
BATCH-57: advance_stage() and ensure_schema_sync() must exist (verified: yes)
BATCH-60: Backend test baseline is 152 (from TASK-02 S2 retry tests)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  152 backend passing, 339 frontend passing
  Expected delta (all Tasks):      +5 backend tests
  Expected total at Batch close:   157 backend passing, 339 frontend passing

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-61/TASK-01 — Per-Proposal Timeout with Graceful Continuation
  Description:      Wrap each proposal synthesis call in asyncio.wait_for() so
                    that a single slow proposal cannot block the entire batch.
                    On timeout, save a placeholder proposal and continue.
  Files in scope:
    - backend/pipeline/orchestrator.py (modify — wrap synthesis calls)
    - backend/pipeline/synthesis/proposal_synthesizer.py (modify — add timeout parameter)
    - backend/tests/test_pipeline/test_proposal_timeout.py (create)
  Depends on:       None
  Required Tests:
    | Test ID          | Type      | Pass Criteria                                         |
    |:-----------------|:----------|:------------------------------------------------------|
    | TEST-61-01-01    | unit      | Single proposal timeout → placeholder saved, batch continues |
    | TEST-61-02-02    | unit      | All proposals succeed → no placeholders, all real proposals  |
    | TEST-61-01-03    | unit      | Timeout value respects 300s cap from HB-01                  |
  Acceptance Criteria:
    AC-01-01: Each proposal synthesis has an independent timeout
    AC-01-02: Timeout produces a placeholder proposal, not a crash
    AC-01-03: Subsequent proposals are still attempted after a timeout

TASK-02: BATCH-61/TASK-02 — Pipeline Stage Persistence + CLI Resume
  Description:      Ensure ideas and gaps are saved to DB immediately after
                    their stages complete. Add --resume RUN_ID CLI flag that
                    skips stages already marked complete in the DB.
  Files in scope:
    - backend/pipeline/orchestrator.py (modify — add intermediate saves)
    - backend/cli/main.py (modify — add --resume flag)
    - backend/tests/test_pipeline/test_resume.py (create)
  Depends on:       TASK-01 (orchestrator changes must not conflict)
  Required Tests:
    | Test ID          | Type      | Pass Criteria                                         |
    |:-----------------|:----------|:------------------------------------------------------|
    | TEST-61-02-01    | unit      | Ideas saved to DB after idea_generation stage completes |
    | TEST-61-02-02    | unit      | Resume skips completed stages, continues from next      |
  Acceptance Criteria:
    AC-02-01: Ideas are queryable from DB before proposals are synthesized
    AC-02-02: --resume RUN_ID skips stages whose current_stage is already past
    AC-02-03: --resume with an invalid RUN_ID produces a clear error message

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Pipeline can survive individual proposal timeouts without crashing
  BAC-02: Pipeline state is queryable from DB at every stage boundary
  BAC-03: CHANGELOG.md updated with BATCH-61 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-61/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

Reviewer Report ID:       REVIEW-BATCH-61-2026-05-04
Review Cycle:             1
Lead Decision:            [x] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

CHK-13 Flag (test ID numbering): Not acted on. Cosmetic issue.
Assistant instructed to use correct sequential TEST-61-01-01/02/03 numbering.

Blueprint Version after response: 1.0 (no revision needed)
Lead Sign:                Lead (Ivory Wolf) 2026-05-04 15:59

═══════════════════════════════════════════════════════════
