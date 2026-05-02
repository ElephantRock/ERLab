BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-11
Blueprint Version:        1.1
Cycle Mode:               STANDARD
Lead Programmer:          Lead
Date Issued:              2026-05-02
Review SLA:               30 minutes
Execution SLA per Task:   90 minutes
Partial Sign-Off SLA:     15 minutes
Task Sequencing:          PARALLEL

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Establish comprehensive test coverage for all 7 existing frontend pages and
key shared components, raising frontend test count from 56 to 140+ and
enabling CI enforcement of ≥70% line coverage.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add test files for all 7 pages: dashboard, pipeline-new, ideas-browser,
    idea-detail, gaps-explorer, knowledge-search, settings
  - Add test files for key components: charts (3), markdown-renderer
  - Each page test covers: render, loading state, empty state, populated
    state (mocked API), API error handling
  - All tests pass in CI (vitest)
  - Coverage threshold enforced: ≥70% lines

What the code MUST NOT do:
  - Modify any existing source components (test files only)
  - Change any existing test files
  - Add new production code
  - Modify any backend files

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: No existing source files (components, pages, hooks, API client)
         may be modified. Only new test files are created.

  HB-02: All existing tests must continue to pass. No regression permitted.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Current frontend test files (9):
  frontend/src/api/__tests__/client.test.ts            — 9 tests
  frontend/src/components/gaps/__tests__/gap-card.test.tsx — 3 tests
  frontend/src/components/ideas/__tests__/feedback-form.test.tsx — 5 tests
  frontend/src/components/ideas/__tests__/score-badge.test.tsx — 4 tests
  frontend/src/components/pipeline/__tests__/run-config-form.test.tsx — 9 tests
  frontend/src/components/pipeline/__tests__/run-progress.test.tsx — 8 tests
  frontend/src/components/pipeline/__tests__/stage-list.test.tsx — 7 tests
  frontend/src/components/pipeline/__tests__/streaming-client.test.ts — 7 tests
  frontend/src/components/ui/__tests__/button.test.tsx — 4 tests
  Total: 56 tests

Test tools: vitest, @testing-library/react, jsdom

Frontend pages to test:
  frontend/src/pages/dashboard.tsx
  frontend/src/pages/pipeline-new.tsx
  frontend/src/pages/ideas-browser.tsx
  frontend/src/pages/idea-detail.tsx
  frontend/src/pages/gaps-explorer.tsx
  frontend/src/pages/knowledge-search.tsx
  frontend/src/pages/settings.tsx

Components to test:
  frontend/src/components/charts/score-distribution.tsx
  frontend/src/components/charts/domain-breakdown.tsx
  frontend/src/components/charts/run-status-chart.tsx
  frontend/src/components/markdown/markdown-renderer.tsx

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: Mock API responses must use the types defined in
         frontend/src/api/types.ts
  AR-02: Test structure follows: describe → it pattern with
         render/act/assert
  AR-03: No real API calls in tests — all HTTP must be mocked

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-10 (error format standardization — mocks must use new error format)
  BATCH-10 status: APPROVED and closed (CERT-BATCH-10-2026-05-02 at docs/aiv/BATCH-10/SIGN-OFF-CERTIFICATE.md)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,438 tests (1,370 backend + 12 new from BATCH-10 + 56 frontend)
  Expected delta (all Tasks):      +29 new frontend tests (20 page + 9 component)
  Expected total at Batch close:   1,467

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-11/TASK-01 — Page Tests
  Description:      Create test files for all 7 frontend pages.
                    Each test covers render, loading, empty, populated, and error states.
  Files in scope:   frontend/src/pages/__tests__/dashboard.test.tsx (NEW)
                    frontend/src/pages/__tests__/pipeline-new.test.tsx (NEW)
                    frontend/src/pages/__tests__/ideas-browser.test.tsx (NEW)
                    frontend/src/pages/__tests__/idea-detail.test.tsx (NEW)
                    frontend/src/pages/__tests__/gaps-explorer.test.tsx (NEW)
                    frontend/src/pages/__tests__/knowledge-search.test.tsx (NEW)
                    frontend/src/pages/__tests__/settings.test.tsx (NEW)
  Depends on:       None
  Required Tests:
    | Test ID          | Type | Pass Criteria                            |
    |:-----------------|:-----|:-----------------------------------------|
    | TEST-11-01-01    | unit | dashboard renders without crashing       |
    | TEST-11-01-02    | unit | dashboard shows loading state            |
    | TEST-11-01-03    | unit | dashboard shows empty state              |
    | TEST-11-01-04    | unit | dashboard shows populated state (mocked) |
    | TEST-11-01-05    | unit | dashboard handles API error              |
    | TEST-11-01-06    | unit | pipeline-new renders without crashing    |
    | TEST-11-01-07    | unit | pipeline-new shows run config form       |
    | TEST-11-01-08    | unit | pipeline-new handles SSE connection error|
    | TEST-11-01-09    | unit | ideas-browser renders idea list          |
    | TEST-11-01-10    | unit | ideas-browser shows empty state          |
    | TEST-11-01-11    | unit | ideas-browser handles API error          |
    | TEST-11-01-12    | unit | idea-detail renders with valid ID        |
    | TEST-11-01-13    | unit | idea-detail shows 404 for missing idea   |
    | TEST-11-01-14    | unit | gaps-explorer renders gap list           |
    | TEST-11-01-15    | unit | gaps-explorer shows empty state          |
    | TEST-11-01-16    | unit | knowledge-search renders search form     |
    | TEST-11-01-17    | unit | knowledge-search shows search results    |
    | TEST-11-01-18    | unit | settings renders form fields             |
    | TEST-11-01-19    | unit | settings saves configuration             |
    | TEST-11-01-20    | unit | settings shows connection error           |
  Acceptance Criteria:
    AC-01-01: All 7 pages have test files
    AC-01-02: Each page test covers render, loading, empty, populated, error
    AC-01-03: All tests pass with `npm test`

TASK-02: BATCH-11/TASK-02 — Component Tests
  Description:      Create test files for chart components and
                    the markdown renderer.
  Files in scope:   frontend/src/components/charts/__tests__/score-distribution.test.tsx (NEW)
                    frontend/src/components/charts/__tests__/domain-breakdown.test.tsx (NEW)
                    frontend/src/components/charts/__tests__/run-status-chart.test.tsx (NEW)
                    frontend/src/components/markdown/__tests__/markdown-renderer.test.tsx (NEW)
                    frontend/vitest.config.ts (MODIFY — add coverage threshold)
  Depends on:       None
  Required Tests:
    | Test ID          | Type | Pass Criteria                              |
    |:-----------------|:-----|:-------------------------------------------|
    | TEST-11-02-01    | unit | score-distribution renders with data       |
    | TEST-11-02-02    | unit | score-distribution renders empty state     |
    | TEST-11-02-03    | unit | domain-breakdown renders with data         |
    | TEST-11-02-04    | unit | domain-breakdown renders empty state       |
    | TEST-11-02-05    | unit | run-status-chart renders with data         |
    | TEST-11-02-06    | unit | run-status-chart renders empty state       |
    | TEST-11-02-07    | unit | markdown-renderer renders basic markdown   |
    | TEST-11-02-08    | unit | markdown-renderer sanitizes dangerous HTML |
    | TEST-11-02-09    | unit | markdown-renderer renders code blocks      |
    | TEST-11-02-10    | unit | vitest coverage threshold set to ≥70% lines |
  Acceptance Criteria:
    AC-02-01: All chart components have test files
    AC-02-02: markdown-renderer handles basic markdown and code blocks
    AC-02-03: All tests pass; `npm test` achieves ≥70% line coverage

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: `npm test` passes with ≥70% frontend line coverage
  BAC-02: CI runs frontend tests successfully
  BAC-03: CHANGELOG.md updated with BATCH-11 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-11/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:       REVIEW-BATCH-11-2026-05-02
Review Cycle:             1
Lead Decision:            [x] ACCEPT WITH MODIFICATIONS

FLAG-01 (CHK-05): Not acted on — BAC-01 (≥70% coverage) implicitly covers
  test count. 140+ is a target, not a hard requirement.
FLAG-02 (CHK-08): Acted on — renumbered second AR-02 to AR-03.
FLAG-03 (CHK-09): Acted on — confirmed BATCH-10 APPROVED and closed in Dependency Map.
FLAG-04 (CHK-13): Partially acted on — added loading/error tests where missing
  for pipeline-new (added TEST-11-01-08) and settings (added TEST-11-01-20).
  Some pages legitimately lack certain states (e.g., gaps-explorer has no
  distinct loading state in the current UI).
FLAG-05 (CHK-14): Acted on — Test Baseline corrected to 1,438 (1,370 backend +
  56 frontend + 12 new from BATCH-10).
FLAG-06 (CHK-16): Acted on — added TEST-11-02-10 to TASK-02 and vitest.config.ts
  to TASK-02 files in scope.
FLAG-07 (CHK-17): Acted on — same fix as CHK-14. All counts now consistent.

Blueprint Version after response: 1.1
Lead Sign:                Lead + 2026-05-02 03:00

═══════════════════════════════════════════════════════════
