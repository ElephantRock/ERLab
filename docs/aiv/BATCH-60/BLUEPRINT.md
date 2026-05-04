BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-60
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
Fix all 71 failing frontend tests by resolving Sentry module
resolution in the test environment, and add exponential backoff
with jitter for Semantic Scholar 429 rate-limit responses.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Mock @sentry/react and initSentry() in the Vitest test environment so all
    339 frontend tests pass without requiring a real Sentry DSN
  - Add retry with exponential backoff + jitter for Semantic Scholar API 429
    responses, allowing the pipeline to eventually succeed instead of silently
    skipping the largest academic search source

What the code MUST NOT do:
  - Must not modify the production Sentry initialization logic
  - Must not add Sentry as a hard dependency for tests (mock only)
  - Must not change the pipeline orchestrator or any stage logic
  - Must not modify any existing passing tests

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Backend:  python -m ruff check backend/
  Frontend: npx tsc --noEmit

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
HB-01: The Sentry mock MUST NOT intercept or modify any production code paths —
       it must exist only in the test setup file (setupTests or vitest config).
HB-02: The S2 retry logic MUST NOT retry more than 5 times per query and MUST
       include a total backoff cap of 120 seconds across all retries.
HB-03: No existing passing test MAY be broken by these changes (both backend
       148 and frontend 339 must remain green).

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Frontend test config:
  - File: frontend/vitest.config.ts (already exists)
  - May need frontend/src/test/setup.ts or setupTests.ts

Semantic Scholar source:
  - File: backend/pipeline/literature/semantic_scholar.py
  - Class: SemanticScholarSource(AcademicSearchSource)
  - Method: async search(query, limit, year_from, year_to) -> list[SearchResult]
  - Uses httpx.AsyncClient with base_url="https://api.semanticscholar.org/graph/v1"
  - Current behavior: logs warning and returns [] on 429

Sentry init:
  - File: frontend/src/lib/sentry.ts (or similar)
  - Function: initSentry() — imports @sentry/react
  - Called from: frontend/src/main.tsx

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
- The test environment mock is authoritative for test execution
- The S2 retry configuration uses settings: retry_max_retries (default 3),
  retry_base_delay (default 1.0), retry_max_delay (default 60.0)
  from existing config.py — no new config fields needed

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
None — this batch is independent of all prior batches.

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  148 backend passing, 71 frontend failing (0 passing effectively due to Sentry import error)
  Expected delta (all Tasks):      +2 backend tests (S2 retry), +0 frontend tests (fix only, no new tests)
  Expected total at Batch close:   150 backend passing, 339 frontend passing

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-60/TASK-01 — Fix Sentry Module Resolution in Frontend Tests
  Description:      Add @sentry/react mock to the Vitest test setup so all 339
                    frontend tests pass without requiring a real Sentry SDK.
  Files in scope:
    - frontend/vitest.config.ts (modify — add setup file reference)
    - frontend/src/test/setup.ts (create — mock @sentry/react and initSentry)
    - frontend/src/main.tsx (may need conditional import guard)
  Depends on:       None
  Required Tests:
    | Test ID          | Type      | Pass Criteria                                    |
    |:-----------------|:----------|:-------------------------------------------------|
    | TEST-60-01-01    | e2e       | `npx vitest run` exits with 0 (all tests pass)   |
    | TEST-60-01-02    | manual    | `npx tsc --noEmit` exits with 0 (no type errors)  |
  Acceptance Criteria:
    AC-01-01: All 339 frontend tests pass with zero failures
    AC-01-02: No modification to production Sentry init logic
    AC-01-03: @sentry/react is fully mocked in test environment

TASK-02: BATCH-60/TASK-02 — Semantic Scholar Rate-Limit Retry with Backoff
  Description:      Add exponential backoff with jitter for HTTP 429 responses
                    in SemanticScholarSource.search(), allowing eventual success
                    instead of silent skip.
  Files in scope:
    - backend/pipeline/literature/semantic_scholar.py (modify — add retry logic)
    - backend/tests/test_pipeline/test_s2_retry.py (create — test retry behavior)
  Depends on:       None
  Required Tests:
    | Test ID          | Type      | Pass Criteria                                           |
    |:-----------------|:----------|:--------------------------------------------------------|
    | TEST-60-02-01    | unit      | Mock 429 response → retry called, eventually returns [] |
    | TEST-60-02-02    | unit      | Mock 429 then 200 → results returned after retry        |
    | TEST-60-02-03    | unit      | Max retries (5) exceeded → returns [] without raising   |
  Acceptance Criteria:
    AC-02-01: 429 responses trigger up to 5 retries with exponential backoff
    AC-02-02: Total backoff cap does not exceed 120 seconds per query
    AC-02-03: Non-429 errors are not retried (existing behavior preserved)
    AC-02-04: All existing backend tests remain passing

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: All frontend tests pass (339+)
  BAC-02: All backend tests pass (150+)
  BAC-03: CHANGELOG.md updated with BATCH-60 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-60/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

Reviewer Report ID:       REVIEW-BATCH-60-2026-05-04
Review Cycle:             1
Lead Decision:            [x] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

CHK-13 Flag (jitter test): Not acted on. Low severity — jitter is a standard
random * delay pattern and does not warrant a dedicated test. If jitter logic
proves problematic, it will surface in integration testing.

Blueprint Version after response: 1.0 (no revision needed)
Lead Sign:                Lead (Ivory Wolf) 2026-05-04 15:39

═══════════════════════════════════════════════════════════
