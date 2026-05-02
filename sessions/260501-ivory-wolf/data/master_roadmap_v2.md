# ELEPHANT ROCK RESEARCH PLATFORM — MASTER ROADMAP
## Aligned to AIV Framework v5.1

**Document Type:** Project Plan — Batch Registry & Cross-Batch Dependency Map  
**Framework:** AIV v5.1 (Architect · Implementer · Verifier)  
**Date Issued:** 2026-05-01  
**Lead Programmer:** [ASSIGNED]  
**Previous Work:** WP-01 through WP-16 (20 commits, no AIV structure)  

---

## HOW TO USE THIS DOCUMENT

This document is the **Batch Registry** for the Elephant Rock roadmap. It is not itself a Blueprint. For each Batch listed below:

1. The Lead extracts the Batch section and issues it as a standalone **Batch Blueprint** (Phase I)
2. The Blueprint is sent to the AI Reviewer Instance (Phase I-B)
3. After Lead Response, the Assistant executes (Phase II)
4. The Lead issues Partial Sign-Offs (Phase II-B) and Batch Certificate (Phase III)
5. All documents are archived under `/docs/aiv/[BATCH-ID]/`

All Batches in this roadmap follow AIV v5.1 conventions, templates, and operational principles.

---

## PROJECT BASELINE

| Metric | Value |
|:---|:---|
| Backend source LOC | 51,044 |
| Backend test functions | 1,303 across 147 test files |
| Frontend source LOC | 3,126 |
| Frontend test cases | 56 across 9 test files |
| Total test baseline | **1,359 tests** |
| API endpoints | 38 |
| Pipeline subpackages | 33 |
| DB tables | 5 |
| Frontend pages | 7 |
| Frontend ↔ Backend parity | ~40% |
| Previous batches under AIV | 0 (WP-01–WP-16 predate AIV adoption) |

---

## BATCH REGISTRY

All Batches are numbered from **BATCH-07** onward (BATCH-01 through BATCH-06 were the 6 real executions referenced in the AIV v5.1 preamble).

| Batch | Roadmap Phase | Cycle Mode | Tasks | Documents | Depends On |
|:---|:---|:---|:---|:---|:---|
| BATCH-07 | 0 — Foundation | SIMPLIFIED | 1 | 3 | None |
| BATCH-08 | 0 — Foundation | SIMPLIFIED | 1 | 3 | None |
| BATCH-09 | 0 — Foundation | SIMPLIFIED | 1 | 3 | None |
| BATCH-10 | 0 — Foundation | STANDARD | 2 | 8 | None |
| BATCH-11 | 0 — Foundation | STANDARD | 2 | 8 | BATCH-10 |
| BATCH-12 | 1 — Core UX | STANDARD | 3 | 10 | BATCH-07 |
| BATCH-13 | 1 — Core UX | STANDARD | 2 | 8 | BATCH-12 |
| BATCH-14 | 1 — Core UX | STANDARD | 2 | 8 | BATCH-12 |
| BATCH-15 | 1 — Core UX | STANDARD | 2 | 8 | BATCH-12 |
| BATCH-16 | 1 — Core UX | STANDARD | 2 | 8 | BATCH-13 |
| BATCH-17 | 1 — Core UX | SIMPLIFIED | 1 | 3 | BATCH-12 |
| BATCH-18 | 2 — Feature Parity | STANDARD | 3 | 10 | BATCH-16 |
| BATCH-19 | 2 — Feature Parity | STANDARD | 3 | 10 | BATCH-16 |
| BATCH-20 | 2 — Feature Parity | STANDARD | 2 | 8 | BATCH-16 |
| BATCH-21 | 2 — Feature Parity | STANDARD | 3 | 10 | BATCH-16 |
| BATCH-22 | 2 — Feature Parity | STANDARD | 3 | 10 | BATCH-16 |
| BATCH-23 | 2 — Feature Parity | STANDARD | 2 | 8 | BATCH-22 |
| BATCH-24 | 2 — Feature Parity | STANDARD | 2 | 8 | BATCH-22 |
| BATCH-25 | 3 — Intelligence | STANDARD | 4 | 12 | BATCH-24 |
| BATCH-26 | 3 — Intelligence | STANDARD | 3 | 10 | BATCH-25 |
| BATCH-27 | 3 — Intelligence | STANDARD | 2 | 8 | BATCH-26 |
| BATCH-28 | 4 — Production | STANDARD | 3 | 10 | BATCH-27 |
| BATCH-29 | 4 — Production | STANDARD | 2 | 8 | BATCH-28 |
| BATCH-30 | 4 — Production | STANDARD | 2 | 8 | BATCH-28 |
| BATCH-31 | 4 — Production | STANDARD | 2 | 8 | BATCH-29, BATCH-30 |
| BATCH-32 | 4 — Production | STANDARD | 2 | 8 | BATCH-31 |
| BATCH-33 | 5 — Growth | STANDARD | 3 | 10 | BATCH-32 |
| BATCH-34 | 5 — Growth | STANDARD | 3 | 10 | BATCH-32 |
| BATCH-35 | 5 — Growth | STANDARD | 3 | 10 | BATCH-33 |
| BATCH-36 | 5 — Growth | SIMPLIFIED | 1 | 3 | BATCH-34 |
| BATCH-37 | 5 — Growth | SIMPLIFIED | 1 | 3 | BATCH-34 |

**Totals: 31 Batches · ~110 Tasks · ~240 Documents**

---

## CROSS-BATCH DEPENDENCY GRAPH

```
BATCH-07 ─┐
BATCH-08 ─┤ Phase 0: Foundation
BATCH-09 ─┤
BATCH-10 ─┼─ BATCH-11
           │
           └──────────────┐
                          ▼
                   BATCH-12 ──┬── BATCH-13 ── BATCH-16
                   (Pipeline   │                  │
                    Results)   ├── BATCH-14       │
                               ├── BATCH-15       │
                               └── BATCH-17       │
                                                  ▼
                                    BATCH-18 ─┐
                                    BATCH-19 ─┤ Phase 2: Feature Parity
                                    BATCH-20 ─┤
                                    BATCH-21 ─┤
                                    BATCH-22 ─┼── BATCH-23
                                              └── BATCH-24
                                                     │
                                                     ▼
                                              BATCH-25 ── BATCH-26 ── BATCH-27
                                                                           │
                                                                           ▼
                                                                    BATCH-28 ──┬─ BATCH-29
                                                                               └─ BATCH-30
                                                                                      │
                                                                               BATCH-31 ── BATCH-32
                                                                                              │
                                                                                     BATCH-33 ── BATCH-35
                                                                                     BATCH-34 ──┬─ BATCH-36
                                                                                                └─ BATCH-37
```

---

## PARALLEL EXECUTION LANES

Batches within the same lane that share no dependency can execute in parallel:

| Lane | Batches | Can Run Simultaneously |
|:---|:---|:---|
| **Lane A** | BATCH-07, BATCH-08, BATCH-09 | Yes — no interdependencies |
| **Lane B** | BATCH-10 → BATCH-11 | Sequential |
| **Lane C** | BATCH-13, BATCH-14, BATCH-15 | After BATCH-12 — parallel with each other |
| **Lane D** | BATCH-18, BATCH-19, BATCH-20, BATCH-21 | After BATCH-16 — parallel with each other |
| **Lane E** | BATCH-23, BATCH-24 | After BATCH-22 — parallel with each other |

**Maximum parallelism:** 5 Batches simultaneously (Lane A + Lane B + Lane C during overlap).

---

═══════════════════════════════════════════════════════════════
# PHASE 0: FOUNDATION & DEVELOPER EXPERIENCE
═══════════════════════════════════════════════════════════════

---

## BATCH-07: Onboarding Wizard

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-07
Blueprint Version:        1.0
Cycle Mode:               SIMPLIFIED
Lead Programmer:          [ASSIGNED]
Date Issued:              [YYYY-MM-DD]
Review SLA:               30 minutes
Execution SLA:            60 minutes

SIMPLIFIED CYCLE ELIGIBILITY — confirm all:
  [x] Exactly 1 Task
  [x] No existing source files modified (new CLI command file only)
  [x] No Hard Boundaries required
  [x] Single deliverable

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Deliver an interactive `erock setup` CLI wizard that takes a new user
from zero configuration to a validated `.env` file and a successful
test pipeline run in under 5 minutes.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What this deliverable MUST contain or do:
  - Interactive Python CLI wizard using `rich` or `click` prompts
  - Detect Python version (≥3.11 required)
  - Offer provider selection: OpenAI / Anthropic / Gemini / Ollama
  - Validate API keys against the chosen provider's health endpoint
  - Detect Ollama at localhost:11434 if selected
  - Write a complete `.env` file with all required variables
  - Optionally run a single-idea test pipeline to confirm end-to-end flow
  - Print next-steps URL for web UI

What it MUST NOT do:
  - Modify any existing source files
  - Require the user to manually edit `.env` after the wizard completes
  - Attempt to install Python or package dependencies

───────────────────────────────────────────────────────────
TASK DEFINITION
───────────────────────────────────────────────────────────
  Description:      Create the `erock setup` interactive CLI command
                    as a new module with wizard flow, provider detection,
                    API key validation, `.env` generation, and optional
                    test pipeline execution.
  Files in scope:   backend/cli/commands/setup.py (NEW)
                    backend/cli/main.py (NEW — command registration line)
  Required Tests:
    | Test ID          | Type     | Pass Criteria                                      |
    |:-----------------|:---------|:---------------------------------------------------|
    | TEST-07-01-01    | unit     | Wizard detects Python <3.11 and exits with error   |
    | TEST-07-01-02    | unit     | Wizard writes complete .env for OpenAI provider     |
    | TEST-07-01-03    | unit     | Wizard writes complete .env for Ollama provider     |
    | TEST-07-01-04    | unit     | Invalid API key detected and user re-prompted       |
    | TEST-07-01-05    | unit     | .env contains all 18 required variables             |
    | TEST-07-01-06    | e2e      | Full wizard run produces working .env (mocked API)  |
  Acceptance Criteria:
    AC-01: `erock setup` completes without error when given valid API key
    AC-02: Generated `.env` allows `erock generate` to succeed immediately
    AC-03: Invalid API keys are caught with a remediation hint, not a traceback

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: `erock setup --provider openai --key sk-...` produces a valid `.env`
          and exits 0 within 60 seconds (mocked API validation)
  BAC-02: CHANGELOG.md updated with BATCH-07 entry
  BAC-03: All documents archived under /docs/aiv/BATCH-07/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:
Review Cycle:             [1 or 2]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS:
  FLAG-01 → Action taken:

If REJECT:

Blueprint Version after response:
Lead Sign:                [Name + YYYY-MM-DD HH:MM]

═══════════════════════════════════════════════════════════
```

---

## BATCH-08: One-Command Start

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-08
Blueprint Version:        1.0
Cycle Mode:               SIMPLIFIED
Lead Programmer:          [ASSIGNED]
Date Issued:              [YYYY-MM-DD]
Review SLA:               30 minutes
Execution SLA:            60 minutes

SIMPLIFIED CYCLE ELIGIBILITY — confirm all:
  [x] Exactly 1 Task
  [x] No existing source files modified (new command file + registration line)
  [x] No Hard Boundaries required
  [x] Single deliverable

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Deliver an `erock dev` CLI command that starts both the backend (uvicorn)
and frontend (npm run dev) in a single terminal with colored log prefixes
and clean Ctrl+C shutdown.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What this deliverable MUST contain or do:
  - Start uvicorn backend on port 8000 as a subprocess
  - Start npm frontend dev server on port 3000 as a subprocess
  - Stream both stdout/stderr to terminal with [BACKEND] / [FRONTEND] prefixes
  - Print both URLs after startup
  - Clean up both processes on Ctrl+C (SIGINT)
  - Detect if ports are already in use and report clearly

What it MUST NOT do:
  - Modify any existing source files
  - Install dependencies or check for node_modules existence
  - Require more than one terminal window

───────────────────────────────────────────────────────────
TASK DEFINITION
───────────────────────────────────────────────────────────
  Description:      Create `erock dev` CLI command that launches both
                    servers as managed subprocesses with unified output
                    and graceful shutdown.
  Files in scope:   backend/cli/commands/dev.py (NEW)
                    backend/cli/main.py (MODIFY — add command registration)
  Required Tests:
    | Test ID          | Type     | Pass Criteria                                      |
    |:-----------------|:---------|:---------------------------------------------------|
    | TEST-08-01-01    | unit     | Command starts uvicorn subprocess with correct args |
    | TEST-08-01-02    | unit     | Command starts npm subprocess with correct args     |
    | TEST-08-01-03    | unit     | SIGINT kills both child processes                   |
    | TEST-08-01-04    | unit     | Port-in-use detected and error reported             |
    | TEST-08-01-05    | integration | Both servers start and respond to health check   |
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

Reviewer Report ID:
Review Cycle:             [1 or 2]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS:
  FLAG-01 → Action taken:

If REJECT:

Blueprint Version after response:
Lead Sign:                [Name + YYYY-MM-DD HH:MM]

═══════════════════════════════════════════════════════════
```

---

## BATCH-09: README Rewrite

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-09
Blueprint Version:        1.0
Cycle Mode:               SIMPLIFIED
Lead Programmer:          [ASSIGNED]
Date Issued:              [YYYY-MM-DD]
Review SLA:               30 minutes
Execution SLA:            60 minutes

SIMPLIFIED CYCLE ELIGIBILITY — confirm all:
  [x] Exactly 1 Task
  [x] No existing source files modified (README.md is documentation)
  [x] No Hard Boundaries required
  [x] Single deliverable

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Deliver a comprehensive README.md that enables a new user to understand
the platform, install it, configure it, and run their first pipeline
within 5 minutes.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What this deliverable MUST contain or do:
  - One-paragraph value proposition ("What is Elephant Rock?")
  - 30-second quick start section referencing `erock setup` and `erock dev`
  - Architecture overview (ASCII diagram or linked image) showing 9-stage pipeline
  - Interface guide covering CLI / Web UI / API
  - Configuration reference link (to docs/)
  - Contributing guide link
  - Project status and version badge (v0.1.0)

What it MUST NOT do:
  - Duplicate the full API reference
  - Reference features that do not yet exist in the codebase
  - Include hardcoded API keys or secrets

───────────────────────────────────────────────────────────
TASK DEFINITION
───────────────────────────────────────────────────────────
  Description:      Complete rewrite of README.md covering value
                    proposition, quick start, architecture, interfaces,
                    and contribution guidelines.
  Files in scope:   README.md (REWRITE)
  Required Tests:   None (documentation only)
  Acceptance Criteria:
    AC-01: README contains a quick start that references `erock setup`
    AC-02: README mentions the web UI and its start command
    AC-03: Architecture section describes the 9-stage pipeline
    AC-04: All referenced CLI commands exist and are correct

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: A new reader can explain the platform's purpose from the first paragraph
  BAC-02: CHANGELOG.md updated with BATCH-09 entry
  BAC-03: All documents archived under /docs/aiv/BATCH-09/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:
Review Cycle:             [1 or 2]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS:
  FLAG-01 → Action taken:

If REJECT:

Blueprint Version after response:
Lead Sign:                [Name + YYYY-MM-DD HH:MM]

═══════════════════════════════════════════════════════════
```

---

## BATCH-10: API Documentation & Error Standardization

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-10
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          [ASSIGNED]
Date Issued:              [YYYY-MM-DD]
Review SLA:               30 minutes
Execution SLA per Task:   60 minutes
Partial Sign-Off SLA:     15 minutes
Task Sequencing:          PARALLEL

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Annotate all 38 API endpoints with descriptions, examples, and response schemas,
and standardize all error responses to a single JSON format with remediation hints.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add `summary` and `description` to every FastAPI route decorator
  - Add `response_model` to endpoints missing it
  - Add example request/response in docstrings
  - Document all error response codes (400, 401, 404, 422, 500)
  - Standardize error format to {"error": {"code": "...", "message": "..."}}
  - Replace all SystemExit calls in provider_factory.py with APIError
  - Add request_id (UUID) header to all error responses

What the code MUST NOT do:
  - Change any endpoint URL paths or HTTP methods
  - Change any success response schemas
  - Remove or rename any existing error types

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: No existing endpoint URL path or HTTP method may be changed.
         Every route must remain backward-compatible.

  HB-02: No SystemExit may remain in any user-facing code path after
         this Batch. All must be replaced with APIError exceptions.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Current error format (inconsistent):
  backend/api/errors.py: HTTPException with {"detail": "..."} or {"error": "..."}
  backend/providers/provider_factory.py: SystemExit on missing API key

Target error format:
  {"error": {"code": "string", "message": "string"}}
  Headers: X-Request-Id: <uuid4>

Current route files:
  backend/api/routes/pipeline.py    — 8 endpoints
  backend/api/routes/ideas.py       — 4 endpoints
  backend/api/routes/gaps.py        — 3 endpoints
  backend/api/routes/knowledge.py   — 4 endpoints
  backend/api/routes/status.py      — 2 endpoints
  backend/api/routes/memory.py      — 6 endpoints
  backend/api/routes/governance.py  — 4 endpoints
  backend/api/routes/costs.py       — 3 endpoints
  backend/api/routes/traces.py      — 4 endpoints

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: Error response format is a global concern. The unified error handler
         in app.py is the single authority for error serialization.
  AR-02: Individual route files may raise domain-specific exceptions but
         MUST NOT serialize error JSON themselves.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  None — this Batch has no dependency on prior Batches.

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,359 existing tests
  Expected delta (all Tasks):      +25 new tests
  Expected total at Batch close:   1,384

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-10/TASK-01 — API Route Annotation
  Description:      Add summary, description, response_model, and example
                    docstrings to all 38 FastAPI route handlers across
                    9 route modules.
  Files in scope:   backend/api/routes/pipeline.py (MODIFY)
                    backend/api/routes/ideas.py (MODIFY)
                    backend/api/routes/gaps.py (MODIFY)
                    backend/api/routes/knowledge.py (MODIFY)
                    backend/api/routes/status.py (MODIFY)
                    backend/api/routes/memory.py (MODIFY)
                    backend/api/routes/governance.py (MODIFY)
                    backend/api/routes/costs.py (MODIFY)
                    backend/api/routes/traces.py (MODIFY)
                    docs/api-guide.md (NEW)
  Depends on:       None
  Required Tests:
    | Test ID          | Type     | Pass Criteria                                         |
    |:-----------------|:---------|:------------------------------------------------------|
    | TEST-10-01-01    | unit     | /docs endpoint returns valid OpenAPI JSON with all 38 paths |
    | TEST-10-01-02    | unit     | Every endpoint has non-empty summary in OpenAPI schema |
    | TEST-10-01-03    | unit     | Every endpoint has at least one response example       |
    | TEST-10-01-04    | integration | docs/api-guide.md contains curl examples for core endpoints |
  Acceptance Criteria:
    AC-01-01: /docs shows complete annotated API with descriptions for every endpoint
    AC-01-02: docs/api-guide.md exists with curl examples

TASK-02: BATCH-10/TASK-02 — Error Standardization
  Description:      Unify error response format across the entire API layer.
                    Replace SystemExit in provider_factory with APIError.
                    Add request_id to error responses.
  Files in scope:   backend/api/errors.py (MODIFY)
                    backend/api/app.py (MODIFY)
                    backend/providers/provider_factory.py (MODIFY)
  Depends on:       None
  Required Tests:
    | Test ID          | Type     | Pass Criteria                                              |
    |:-----------------|:---------|:-----------------------------------------------------------|
    | TEST-10-02-01    | unit     | APIError serializes to {"error": {"code": ..., "message": ...}} |
    | TEST-10-02-02    | unit     | 400 response has correct JSON format and X-Request-Id header |
    | TEST-10-02-03    | unit     | 401 response has correct JSON format and remediation hint    |
    | TEST-10-02-04    | unit     | 404 response has correct JSON format                        |
    | TEST-10-02-05    | unit     | 422 response has correct JSON format                        |
    | TEST-10-02-06    | unit     | 500 response has correct JSON format                        |
    | TEST-10-02-07    | unit     | provider_factory raises APIError (not SystemExit) on missing key |
    | TEST-10-02-08    | integration | End-to-end invalid request produces standardized error    |
  Acceptance Criteria:
    AC-02-01: No SystemExit remains in provider_factory.py user-facing paths
    AC-02-02: All error responses have {"error": {"code", "message"}} format
    AC-02-03: All error responses include X-Request-Id header
    AC-02-04: 401 errors include a remediation hint ("Check your API key...")

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: /docs endpoint shows a fully annotated API reference
  BAC-02: Every error response uses the standardized JSON format
  BAC-03: CHANGELOG.md updated with BATCH-10 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-10/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:
Review Cycle:             [1 or 2]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS — list each Reviewer flag acted on:
  FLAG-01 → Action taken:
  FLAG-02 → Action taken:

If REJECT — reason and next action:

Blueprint Version after response: [Increment if revised]
Lead Sign:                [Name + YYYY-MM-DD HH:MM]

═══════════════════════════════════════════════════════════
```

---

## BATCH-11: Frontend Test Infrastructure

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-11
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          [ASSIGNED]
Date Issued:              [YYYY-MM-DD]
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
  - Add test files for key components: charts (3), markdown-renderer, gap-card
  - Each page test covers: render, loading state, empty state, populated state,
    API error handling
  - All tests pass in CI (vitest)
  - Coverage threshold enforced: ≥70% lines

What the code MUST NOT do:
  - Modify any existing source components (test files only)
  - Change any existing test files
  - Add new production code

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
  frontend/src/api/__tests__/client.test.ts           — 9 tests
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

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: Mock API responses must use the types defined in frontend/src/api/types.ts
  AR-02: Test structure follows: describe → it pattern with render/act/assert

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-10 (error format standardization — tests must match new error format)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,359 tests (1,303 backend + 56 frontend)
  Expected delta (all Tasks):      +84 new frontend tests
  Expected total at Batch close:   1,443

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
    | TEST-11-01-06..10| unit | (Same 5 patterns for each of 6 remaining pages) |
    | TEST-11-01-11..35| unit | 35 tests total across 7 pages (5 each)  |
  Acceptance Criteria:
    AC-01-01: All 7 pages have test files
    AC-01-02: Each page test covers render, loading, empty, populated, error
    AC-01-03: All tests pass with `npm test`

TASK-02: BATCH-11/TASK-02 — Component Tests
  Description:      Create test files for key shared components:
                    charts, markdown-renderer, and enhance gap-card coverage.
  Files in scope:   frontend/src/components/charts/__tests__/score-distribution.test.tsx (NEW)
                    frontend/src/components/charts/__tests__/domain-breakdown.test.tsx (NEW)
                    frontend/src/components/charts/__tests__/run-status-chart.test.tsx (NEW)
                    frontend/src/components/markdown/__tests__/markdown-renderer.test.tsx (NEW)
  Depends on:       None
  Required Tests:
    | Test ID          | Type | Pass Criteria                              |
    |:-----------------|:-----|:-------------------------------------------|
    | TEST-11-02-01    | unit | score-distribution renders with data       |
    | TEST-11-02-02    | unit | score-distribution renders empty state     |
    | TEST-11-02-03    | unit | domain-breakdown renders with data         |
    | TEST-11-02-04    | unit | domain-breakdown renders empty state       |
    | TEST-11-02-05    | unit | run-status-chart renders with data         |
    | TEST-11-02-06    | unit | markdown-renderer renders basic markdown   |
    | TEST-11-02-07    | unit | markdown-renderer sanitizes dangerous HTML |
    | TEST-11-02-08    | unit | markdown-renderer renders code blocks      |
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

Reviewer Report ID:
Review Cycle:             [1 or 2]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS — list each Reviewer flag acted on:
  FLAG-01 → Action taken:

If REJECT — reason and next action:

Blueprint Version after response: [Increment if revised]
Lead Sign:                [Name + YYYY-MM-DD HH:MM]

═══════════════════════════════════════════════════════════
```

---

═══════════════════════════════════════════════════════════════
# PHASE 1: CORE UX — THE GOLDEN PATH
═══════════════════════════════════════════════════════════════

---

## BATCH-12: Pipeline Results Flow & Run Detail

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-12
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          [ASSIGNED]
Date Issued:              [YYYY-MM-DD]
Review SLA:               30 minutes
Execution SLA per Task:   90 minutes
Partial Sign-Off SLA:     15 minutes
Task Sequencing:          SEQUENTIAL

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Connect pipeline completion to results display. After a pipeline run finishes,
the user sees generated ideas inline on the pipeline page and can navigate
to a dedicated Run Detail page showing full metadata, stages, and results.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add GET /api/v1/pipeline/runs/{run_id}/ideas endpoint returning ideas for a run
  - Show inline results section on pipeline-new page after completion
  - Create a new /runs/:id route and page showing full run detail
  - Make RunCard components on Dashboard clickable (navigate to /runs/:id)
  - Show pipeline summary stats (ideas found, gaps identified, time elapsed)

What the code MUST NOT do:
  - Change the existing pipeline execution flow or SSE event protocol
  - Modify the ideas table schema or ideas API endpoints
  - Remove or replace any existing dashboard components

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: The existing SSE streaming protocol (event types, payload formats)
         MUST NOT be altered. New results display consumes the existing
         stream output, not the other way around.

  HB-02: The new /runs/{id}/ideas endpoint MUST be read-only.
         No data mutation endpoint may be introduced in this Batch.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Existing models (backend/db/models.py):
  class PipelineRun:
    id: str (UUID)
    domain: str
    status: str  # pending/running/completed/failed
    config_json: str
    result_json: str
    stages_completed: str (JSON list)
    error_message: str | None
    created_at: datetime
    updated_at: datetime

Existing API (backend/api/routes/pipeline.py):
  GET /runs/detail/{id} → PipelineRunDetail (already exists, not exposed in frontend)

New endpoint:
  GET /api/v1/pipeline/runs/{run_id}/ideas
  → { ideas: IdeaSummary[], total: int }

Frontend types (frontend/src/api/types.ts):
  PipelineRun, PipelineRunDetail, IdeaSummary — already defined

Frontend API (frontend/src/api/pipeline.ts):
  getRunDetail(id) — already defined, unused

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: Idea data for a run is sourced from the ideas table filtered by
         run_id, not from PipelineRun.result_json. The relational query
         is the authority.
  AR-02: Run navigation is URL-based (/runs/:id). No modal or drawer.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-07 (CLI setup command — so the end-to-end flow works for testing)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,443 tests
  Expected delta (all Tasks):      +30 new tests
  Expected total at Batch close:   1,473

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-12/TASK-01 — Backend: Run Ideas Endpoint
  Description:      Add a new read-only endpoint that returns all ideas
                    generated by a specific pipeline run.
  Files in scope:   backend/api/routes/pipeline.py (MODIFY)
                    backend/db/crud.py (MODIFY)
  Depends on:       None
  Required Tests:
    | Test ID          | Type        | Pass Criteria                                  |
    |:-----------------|:------------|:-----------------------------------------------|
    | TEST-12-01-01    | unit        | get_ideas_for_run returns correct ideas         |
    | TEST-12-01-02    | unit        | get_ideas_for_run returns empty list for no ideas|
    | TEST-12-01-03    | integration | GET /runs/{id}/ideas returns 200 with ideas     |
    | TEST-12-01-04    | integration | GET /runs/{invalid}/ideas returns 404           |
    | TEST-12-01-05    | unit        | Response includes total count field             |
  Acceptance Criteria:
    AC-01-01: GET /runs/{id}/ideas returns ideas linked to that run
    AC-01-02: Response format is { ideas: IdeaSummary[], total: int }
    AC-01-03: 404 returned for non-existent run IDs

TASK-02: BATCH-12/TASK-02 — Frontend: Pipeline Results Display
  Description:      Add inline results section to pipeline-new page
                    that appears after pipeline completion showing
                    generated ideas with navigation links.
  Files in scope:   frontend/src/pages/pipeline-new.tsx (MODIFY)
                    frontend/src/api/pipeline.ts (MODIFY — add getRunIdeas)
  Depends on:       TASK-01 (needs backend endpoint)
  Required Tests:
    | Test ID          | Type | Pass Criteria                                          |
    |:-----------------|:-----|:-------------------------------------------------------|
    | TEST-12-02-01    | unit | Results section renders after pipeline completion       |
    | TEST-12-02-02    | unit | Shows "Pipeline Complete" banner with summary stats     |
    | TEST-12-02-03    | unit | Generated ideas appear as IdeaCards                    |
    | TEST-12-02-04    | unit | "View All Ideas" button links to /ideas                 |
    | TEST-12-02-05    | unit | "Run Another" button resets form state                  |
    | TEST-12-02-06    | unit | Empty results shows appropriate message                 |
  Acceptance Criteria:
    AC-02-01: Results appear within 2 seconds of pipeline completion
    AC-02-02: User can click through to any idea from the results section
    AC-02-03: "Run Another" resets the form cleanly

TASK-03: BATCH-12/TASK-03 — Frontend: Run Detail Page
  Description:      Create a new Run Detail page at /runs/:id showing
                    full run metadata, stages timeline, generated ideas,
                    cost summary, and actions (resume/delete).
  Files in scope:   frontend/src/pages/run-detail.tsx (NEW)
                    frontend/src/App.tsx (MODIFY — add route)
                    frontend/src/components/pipeline/run-card.tsx (MODIFY — add onClick)
                    frontend/src/pages/dashboard.tsx (MODIFY — clickable RunCards)
  Depends on:       TASK-01 (needs backend endpoint)
  Required Tests:
    | Test ID          | Type | Pass Criteria                                      |
    |:-----------------|:-----|:---------------------------------------------------|
    | TEST-12-03-01    | unit | Run detail page renders with valid run data        |
    | TEST-12-03-02    | unit | Shows run metadata (ID, domain, status, timestamps)|
    | TEST-12-03-03    | unit | Shows stages timeline with completion status       |
    | TEST-12-03-04    | unit | Shows generated ideas list                         |
    | TEST-12-03-05    | unit | Shows error message for failed runs                |
    | TEST-12-03-06    | unit | Resume button appears only for failed runs         |
    | TEST-12-03-07    | unit | RunCard click navigates to /runs/:id               |
    | TEST-12-03-08    | unit | 404 run shows "Run not found" message              |
  Acceptance Criteria:
    AC-03-01: Clicking a RunCard on Dashboard navigates to /runs/:id
    AC-03-02: Run detail shows all metadata, stages, and ideas
    AC-03-03: Failed runs show error message prominently
    AC-03-04: Resume button appears only for failed/interrupted runs

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: End-to-end: start pipeline → see results → click to run detail → see full info
  BAC-02: No existing SSE streaming behavior is altered
  BAC-03: CHANGELOG.md updated with BATCH-12 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-12/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:
Review Cycle:             [1 or 2]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS — list each Reviewer flag acted on:
  FLAG-01 → Action taken:
  FLAG-02 → Action taken:

If REJECT — reason and next action:

Blueprint Version after response: [Increment if revised]
Lead Sign:                [Name + YYYY-MM-DD HH:MM]

═══════════════════════════════════════════════════════════
```

---

## BATCH-13: Pipeline Form Completion & Settings Enhancement

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-13
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          [ASSIGNED]
Date Issued:              [YYYY-MM-DD]
Review SLA:               30 minutes
Execution SLA per Task:   60 minutes
Partial Sign-Off SLA:     15 minutes
Task Sequencing:          PARALLEL

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Expose all backend pipeline options in the frontend form and enhance
the settings page with backend connectivity check, version display,
and default domain persistence.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add generation_rounds, export_format to pipeline form
  - Add toggle switches for run_novelty, run_feasibility, run_synthesis
  - Collapsible "Advanced Options" section to avoid overwhelming new users
  - Fix max_gaps range (1-20, not 1-50) to match API validation
  - Add "Test Connection" button to settings
  - Add connection status indicator (green/red dot)
  - Add version display and default provider name
  - Add default domain setting saved to localStorage
  - Add GET /api/v1/status/detailed endpoint

What the code MUST NOT do:
  - Change backend validation rules (form must match existing rules)
  - Remove any existing form fields
  - Modify the pipeline execution engine

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Form validation MUST match API validation exactly. The API
         is the authority for all validation rules. No client-side
         validation rule may be stricter or more lenient than the
         corresponding API validation.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Backend config (backend/config.py):
  generation_rounds: int = 3 (range 1-10)
  export_format: str = "markdown" (markdown|latex|none)
  run_novelty: bool = True
  run_feasibility: bool = True
  run_synthesis: bool = True
  max_gaps: int = 10 (range 1-20, NOT 1-50)

Frontend form current state (run-config-form.tsx):
  Missing: generation_rounds, export_format, run_novelty, run_feasibility, run_synthesis
  Bug: max_gaps range set to 1-50, should be 1-20

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: Default values come from GET /api/v1/settings (backend config).
         localStorage defaults are fallback only.
  AR-02: Default domain is a frontend-only concern stored in localStorage.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-12 (pipeline form is part of the pipeline page)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,473 tests
  Expected delta (all Tasks):      +18 new tests
  Expected total at Batch close:   1,491

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-13/TASK-01 — Pipeline Form Completion
  Description:      Add missing backend options to the pipeline
                    configuration form with proper validation.
  Files in scope:   frontend/src/components/pipeline/run-config-form.tsx (MODIFY)
                    frontend/src/api/types.ts (MODIFY — if type gaps exist)
  Depends on:       None
  Required Tests:
    | Test ID          | Type | Pass Criteria                                      |
    |:-----------------|:-----|:---------------------------------------------------|
    | TEST-13-01-01    | unit | generation_rounds input renders with range 1-10     |
    | TEST-13-01-02    | unit | export_format dropdown renders with 3 options       |
    | TEST-13-01-03    | unit | Advanced section is collapsed by default            |
    | TEST-13-01-04    | unit | Toggles for novelty/feasibility/synthesis render    |
    | TEST-13-01-05    | unit | max_gaps range is 1-20 (not 1-50)                  |
    | TEST-13-01-06    | unit | Form submission includes all new fields             |
  Acceptance Criteria:
    AC-01-01: All backend pipeline options are exposed in the form
    AC-01-02: Form validation matches API validation exactly
    AC-01-03: Advanced options collapsed by default

TASK-02: BATCH-13/TASK-02 — Settings Enhancement
  Description:      Enhance settings page with backend connectivity
                    test, version display, and persistent defaults.
  Files in scope:   frontend/src/pages/settings.tsx (MODIFY)
                    frontend/src/api/client.ts (MODIFY — add testConnection)
                    backend/api/routes/status.py (MODIFY — add /detailed)
  Depends on:       None
  Required Tests:
    | Test ID          | Type | Pass Criteria                                        |
    |:-----------------|:-----|:-----------------------------------------------------|
    | TEST-13-02-01    | unit | Test Connection button calls /health endpoint         |
    | TEST-13-02-02    | unit | Green dot shown when backend is reachable             |
    | TEST-13-02-03    | unit | Red dot shown when backend is unreachable             |
    | TEST-13-02-04    | unit | Version display shows backend version string          |
    | TEST-13-02-05    | unit | Default domain saved to localStorage                  |
    | TEST-13-02-06    | unit | Default domain loaded from localStorage on mount      |
    | TEST-13-02-07    | integration | GET /status/detailed returns version + provider  |
  Acceptance Criteria:
    AC-02-01: Settings page shows backend connection status at all times
    AC-02-02: "Test Connection" gives immediate feedback
    AC-02-03: Default domain pre-fills in pipeline form

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Pipeline form exposes all backend options with correct validation
  BAC-02: Settings page provides live connectivity feedback
  BAC-03: CHANGELOG.md updated with BATCH-13 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-13/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:
Review Cycle:             [1 or 2]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS — list each Reviewer flag acted on:
  FLAG-01 → Action taken:

If REJECT — reason and next action:

Blueprint Version after response: [Increment if revised]
Lead Sign:                [Name + YYYY-MM-DD HH:MM]

═══════════════════════════════════════════════════════════
```

---

## BATCH-14: Ideas Browser Enhancement & Gap-Idea Traceability

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-14
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          [ASSIGNED]
Date Issued:              [YYYY-MM-DD]
Review SLA:               30 minutes
Execution SLA per Task:   60 minutes
Partial Sign-Off SLA:     15 minutes
Task Sequencing:          SEQUENTIAL

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Transform the Ideas Browser from a static list into a sortable, filterable,
searchable interface, and establish bidirectional traceability between
research gaps and generated ideas.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add sort dropdown to Ideas Browser (score, novelty, feasibility, date)
  - Add min_score slider filter (0.0-1.0)
  - Add search input for full-text keyword search
  - Show overall score badge on IdeaCard
  - Add proposal indicator icon on cards with existing proposals
  - Backend: add search and sort params to GET /ideas
  - Backend: add idea count per gap in gap responses
  - Backend: include source_gap_ids in idea responses
  - Frontend: GapCard shows "N ideas generated" badge
  - Frontend: Idea Detail shows source gaps section

What the code MUST NOT do:
  - Remove existing pagination on Ideas Browser
  - Change the gap scoring or idea scoring algorithms
  - Modify the knowledge graph data model

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Full-text search on ideas MUST use parameterized queries only.
         No string interpolation into SQL. SQL injection is a hard boundary.

  HB-02: The idea scoring algorithm MUST NOT be altered. Only display
         and sorting of existing scores is in scope.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Existing (backend/db/models.py):
  class Idea: id, title, description, domain, novelty_score, feasibility_score,
              overall_score, source_gap_ids (JSON), proposal_text, run_id, created_at

  class ResearchGap: id, title, description, gap_type, domain, confidence_score,
                      sources (JSON), status, created_at

New backend params:
  GET /api/v1/ideas?search=keyword&sort_by=score|novelty|feasibility|date&sort_order=desc|asc&min_score=0.7

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: source_gap_ids in the Idea model is the authority for gap→idea
         relationships. No secondary relationship table is created.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-12 (ideas display components used from pipeline results)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,491 tests
  Expected delta (all Tasks):      +20 new tests
  Expected total at Batch close:   1,511

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-14/TASK-01 — Backend: Sort, Search, Traceability
  Description:      Add search/sort query parameters to the ideas endpoint,
                    add idea count to gap responses, and include source_gap_ids
                    in idea responses.
  Files in scope:   backend/api/routes/ideas.py (MODIFY)
                    backend/api/routes/gaps.py (MODIFY)
                    backend/db/crud.py (MODIFY)
  Depends on:       None
  Required Tests:
    | Test ID          | Type        | Pass Criteria                                    |
    |:-----------------|:------------|:-------------------------------------------------|
    | TEST-14-01-01    | unit        | search param filters ideas by title keyword       |
    | TEST-14-01-02    | unit        | sort_by=score returns ideas ordered by score desc |
    | TEST-14-01-03    | unit        | min_score=0.7 returns only ideas ≥ 0.7            |
    | TEST-14-01-04    | unit        | count_ideas_for_gap returns correct count         |
    | TEST-14-01-05    | integration | GET /ideas?search=test returns matching ideas     |
    | TEST-14-01-06    | integration | GET /gaps includes idea_count field               |
    | TEST-14-01-07    | unit        | SQL injection attempt returns sanitized results   |
  Acceptance Criteria:
    AC-01-01: Ideas can be sorted by score, novelty, feasibility, date
    AC-01-02: Full-text search works on title field
    AC-01-03: Gap responses include idea count
    AC-01-04: Idea responses include source_gap_ids

TASK-02: BATCH-14/TASK-02 — Frontend: Ideas & Gaps UX
  Description:      Enhance Ideas Browser with sort/filter/search UI,
                    add score badges to IdeaCards, add proposal indicator,
                    enhance GapCard with idea count badge, and show source
                    gaps on Idea Detail.
  Files in scope:   frontend/src/pages/ideas-browser.tsx (MODIFY)
                    frontend/src/pages/idea-detail.tsx (MODIFY)
                    frontend/src/pages/gaps-explorer.tsx (MODIFY)
                    frontend/src/components/ideas/idea-card.tsx (MODIFY)
                    frontend/src/components/gaps/gap-card.tsx (MODIFY)
                    frontend/src/api/ideas.ts (MODIFY — add params)
  Depends on:       TASK-01 (needs backend endpoint changes)
  Required Tests:
    | Test ID          | Type | Pass Criteria                                      |
    |:-----------------|:-----|:---------------------------------------------------|
    | TEST-14-02-01    | unit | Sort dropdown renders with 4 options               |
    | TEST-14-02-02    | unit | Min score slider renders with 0-1 range            |
    | TEST-14-02-03    | unit | Search input filters ideas by keyword              |
    | TEST-14-02-04    | unit | IdeaCard shows overall score badge                 |
    | TEST-14-02-05    | unit | IdeaCard shows proposal icon when proposal exists  |
    | TEST-14-02-06    | unit | GapCard shows "N ideas generated" badge            |
    | TEST-14-02-07    | unit | GapCard badge click navigates to filtered ideas    |
    | TEST-14-02-08    | unit | Idea Detail shows source gaps section              |
  Acceptance Criteria:
    AC-02-01: User can sort ideas by any score dimension
    AC-02-02: Min score filter works in real-time
    AC-02-03: Bidirectional gap↔idea navigation works via clicks

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Ideas Browser is sortable, filterable, and searchable
  BAC-02: Gap↔Idea traceability works in both directions
  BAC-03: CHANGELOG.md updated with BATCH-14 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-14/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:
Review Cycle:             [1 or 2]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS — list each Reviewer flag acted on:
  FLAG-01 → Action taken:

If REJECT — reason and next action:

Blueprint Version after response: [Increment if revised]
Lead Sign:                [Name + YYYY-MM-DD HH:MM]

═══════════════════════════════════════════════════════════
```

---

## BATCH-15: Cancel Pipeline from UI

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-15
Blueprint Version:        1.0
Cycle Mode:               SIMPLIFIED
Lead Programmer:          [ASSIGNED]
Date Issued:              [YYYY-MM-DD]
Review SLA:               30 minutes
Execution SLA:            60 minutes

SIMPLIFIED CYCLE ELIGIBILITY — confirm all:
  [x] Exactly 1 Task
  [x] No existing source files modified (wait — modifies pipeline-new.tsx)
  [ ] No existing source files modified
  ⇒ NOT ELIGIBLE FOR SIMPLIFIED — switching to STANDARD

═══

Batch ID:                 BATCH-15
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          [ASSIGNED]
Date Issued:              [YYYY-MM-DD]
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
  DELETE /api/v1/pipeline/runs/{run_id} → already implemented

Existing frontend API (frontend/src/api/pipeline.ts):
  cancelRun(runId: string) → already defined, unused

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: Cancellation requires explicit user confirmation.
         No automatic or timeout-based cancellation.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-12 (pipeline page structure)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,511 tests
  Expected delta (all Tasks):      +5 new tests
  Expected total at Batch close:   1,516

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
    AC-01-01: Cancel button appears during pipeline execution
    AC-01-02: Confirmation dialog prevents accidental cancellation
    AC-01-03: Cancelled runs show partial results

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: User can cancel a running pipeline from the UI
  BAC-02: CHANGELOG.md updated with BATCH-15 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-15/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:
Review Cycle:             [1 or 2]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS — list each Reviewer flag acted on:
  FLAG-01 → Action taken:

If REJECT — reason and next action:

Blueprint Version after response: [Increment if revised]
Lead Sign:                [Name + YYYY-MM-DD HH:MM]

═══════════════════════════════════════════════════════════
```

---

## BATCH-16: Navigation & Routing Infrastructure

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-16
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          [ASSIGNED]
Date Issued:              [YYYY-MM-DD]
Review SLA:               30 minutes
Execution SLA per Task:   60 minutes
Partial Sign-Off SLA:     15 minutes
Task Sequencing:          SEQUENTIAL

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Extend the frontend routing and navigation infrastructure to support the
upcoming Feature Parity pages (costs, memory, governance, traces, sessions,
literature) by adding sidebar nav items, route definitions, and a consistent
page layout pattern.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add sidebar nav items for: Costs, Memory, Governance, Traces, Sessions, Literature
  - Add placeholder routes in App.tsx for each new page
  - Each placeholder shows "Coming Soon" with the page title
  - Use Lucide icons consistent with existing sidebar pattern
  - Maintain existing nav items (Dashboard, Pipeline, Ideas, Gaps, Knowledge, Settings)

What the code MUST NOT do:
  - Remove or reorder existing nav items
  - Create full page implementations (placeholders only)
  - Modify any existing page components

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Existing navigation items and their routes MUST NOT change.
         New items are appended after existing ones.

  HB-02: Placeholder pages MUST NOT make API calls. They are static.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Current routes (frontend/src/App.tsx):
  / → Dashboard
  /pipeline/new → PipelineNew
  /ideas → IdeasBrowser
  /ideas/:id → IdeaDetail
  /gaps → GapsExplorer
  /knowledge → KnowledgeSearch
  /settings → Settings

Current sidebar items (frontend/src/components/layout/sidebar.tsx):
  Dashboard (LayoutDashboard), Pipeline (PlayCircle), Ideas (Lightbulb),
  Gaps (Search), Knowledge (BookOpen), Settings (Settings)

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: Sidebar ordering: existing items first, then new items in the order
         they appear in the Phase 2 roadmap.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-13 (settings enhancement must be complete before nav changes)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,516 tests
  Expected delta (all Tasks):      +10 new tests
  Expected total at Batch close:   1,526

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-16/TASK-01 — Navigation Extension
  Description:      Add sidebar items and placeholder routes for all
                    Phase 2 pages, with "Coming Soon" placeholders.
  Files in scope:   frontend/src/components/layout/sidebar.tsx (MODIFY)
                    frontend/src/App.tsx (MODIFY)
                    frontend/src/pages/placeholder.tsx (NEW)
  Depends on:       None
  Required Tests:
    | Test ID          | Type | Pass Criteria                                        |
    |:-----------------|:-----|:-----------------------------------------------------|
    | TEST-16-01-01    | unit | Sidebar renders all 12 nav items (6 existing + 6 new)|
    | TEST-16-01-02    | unit | Existing nav items unchanged in order and label      |
    | TEST-16-01-03    | unit | New nav items use correct Lucide icons               |
    | TEST-16-01-04    | unit | /costs route renders placeholder with "Costs" title  |
    | TEST-16-01-05    | unit | /memory route renders placeholder                    |
    | TEST-16-01-06    | unit | /governance route renders placeholder                |
    | TEST-16-01-07    | unit | /traces route renders placeholder                    |
    | TEST-16-01-08    | unit | /sessions route renders placeholder                  |
    | TEST-16-01-09    | unit | /literature route renders placeholder                |
    | TEST-16-01-10    | unit | Placeholder pages do not make API calls              |
  Acceptance Criteria:
    AC-01-01: All 6 new sidebar items are visible and navigable
    AC-01-02: All existing nav items remain unchanged
    AC-01-03: Placeholder pages show "Coming Soon" with correct title

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: All Phase 2 pages are accessible via sidebar navigation
  BAC-02: CHANGELOG.md updated with BATCH-16 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-16/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:
Review Cycle:             [1 or 2]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS — list each Reviewer flag acted on:
  FLAG-01 → Action taken:

If REJECT — reason and next action:

Blueprint Version after response: [Increment if revised]
Lead Sign:                [Name + YYYY-MM-DD HH:MM]

═══════════════════════════════════════════════════════════
```

---

## BATCH-17: CHANGELOG.md Creation

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-17
Blueprint Version:        1.0
Cycle Mode:               SIMPLIFIED
Lead Programmer:          [ASSIGNED]
Date Issued:              [YYYY-MM-DD]
Review SLA:               30 minutes
Execution SLA:            60 minutes

SIMPLIFIED CYCLE ELIGIBILITY — confirm all:
  [x] Exactly 1 Task
  [x] No existing source files modified (new documentation file only)
  [x] No Hard Boundaries required
  [x] Single deliverable

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Create CHANGELOG.md documenting the complete project history from
initial commit through WP-16, establishing the changelog discipline
required by AIV BAC-03.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What this deliverable MUST contain or do:
  - Chronological changelog following Keep a Changelog format
  - Entries for all 20 commits (initial + WP-01 through WP-16)
  - Categories: Added, Changed, Fixed, Deprecated, Removed, Security
  - Version header for v0.1.0 (current)
  - [Unreleased] section for upcoming work

What it MUST NOT do:
  - Describe features that do not exist in the codebase
  - Include speculative future entries

───────────────────────────────────────────────────────────
TASK DEFINITION
───────────────────────────────────────────────────────────
  Description:      Create CHANGELOG.md with complete project history.
  Files in scope:   CHANGELOG.md (NEW)
  Required Tests:   None (documentation only)
  Acceptance Criteria:
    AC-01: CHANGELOG.md exists with entries for WP-01 through WP-16
    AC-02: Format follows Keep a Changelog conventions
    AC-03: [Unreleased] section exists for future entries

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: CHANGELOG.md accurately documents all 20 commits
  BAC-03: All documents archived under /docs/aiv/BATCH-17/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:
Review Cycle:             [1 or 2]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS:
  FLAG-01 → Action taken:

If REJECT:

Blueprint Version after response:
Lead Sign:                [Name + YYYY-MM-DD HH:MM]

═══════════════════════════════════════════════════════════
```

---

═══════════════════════════════════════════════════════════════
# PHASE 2: FEATURE PARITY — FRONTEND MEETS BACKEND
═══════════════════════════════════════════════════════════════

> **Batches BATCH-18 through BATCH-24 follow the same Standard Cycle structure.
> Full Blueprint templates for these batches are provided below.**
> All depend on BATCH-16 (navigation infrastructure with placeholder routes).

---

## BATCH-18: Cost Dashboard

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-18
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          [ASSIGNED]
Date Issued:              [YYYY-MM-DD]
Review SLA:               30 minutes
Execution SLA per Task:   90 minutes
Partial Sign-Off SLA:     15 minutes
Task Sequencing:          SEQUENTIAL

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Deliver a Cost Dashboard page showing total spend, cost breakdowns by
provider/stage/model, per-run costs, and budget utilization.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Replace /costs placeholder with full Cost Dashboard page
  - Create API client for cost endpoints (already exist in backend)
  - Show total spend: today, this week, all time
  - Cost by provider (pie chart), by stage (bar chart), by model (table)
  - Per-run cost breakdown list
  - Budget utilization bar (current vs configured limit)

What the code MUST NOT do:
  - Modify existing backend cost endpoints or cost tracking logic
  - Create new backend endpoints (all cost data is already available)
  - Store cost data on the frontend

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: No backend modifications. All cost endpoints already exist:
         GET /api/v1/costs/summary, GET /api/v1/costs/by-model,
         GET /api/v1/costs/by-stage, GET /api/v1/costs/runs/{id}

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Existing backend endpoints (backend/api/routes/costs.py):
  GET /api/v1/costs/summary     → CostSummary
  GET /api/v1/costs/by-model    → CostByModel[]
  GET /api/v1/costs/by-stage    → CostByStage[]
  GET /api/v1/costs/runs/{id}   → RunCostBreakdown

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: Cost data is read-only from the frontend perspective.
         No cost manipulation endpoints are called.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-16 (placeholder route must exist)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,526 tests
  Expected delta (all Tasks):      +18 new tests
  Expected total at Batch close:   1,544

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-18/TASK-01 — Cost API Client
  Description:      Create frontend API client module for the existing
                    cost endpoints.
  Files in scope:   frontend/src/api/costs.ts (NEW)
  Depends on:       None
  Required Tests:
    | Test ID          | Type | Pass Criteria                                   |
    |:-----------------|:-----|:------------------------------------------------|
    | TEST-18-01-01    | unit | getCostSummary() calls correct endpoint          |
    | TEST-18-01-02    | unit | getCostByModel() returns typed response          |
    | TEST-18-01-03    | unit | getCostByStage() returns typed response          |
    | TEST-18-01-04    | unit | getRunCostBreakdown(id) calls correct endpoint   |
  Acceptance Criteria:
    AC-01-01: All 4 cost API functions work with correct types

TASK-02: BATCH-18/TASK-02 — Cost Charts
  Description:      Create chart components for cost visualization.
  Files in scope:   frontend/src/components/charts/cost-over-time.tsx (NEW)
                    frontend/src/components/charts/cost-by-stage.tsx (NEW)
  Depends on:       TASK-01
  Required Tests:
    | Test ID          | Type | Pass Criteria                                   |
    |:-----------------|:-----|:------------------------------------------------|
    | TEST-18-02-01    | unit | cost-over-time renders with data                 |
    | TEST-18-02-02    | unit | cost-over-time renders empty state               |
    | TEST-18-02-03    | unit | cost-by-stage renders bar chart with data        |
    | TEST-18-02-04    | unit | cost-by-stage renders empty state                |
  Acceptance Criteria:
    AC-02-01: Charts render correctly with cost data
    AC-02-02: Charts show appropriate empty states

TASK-03: BATCH-18/TASK-03 — Cost Dashboard Page
  Description:      Replace placeholder with full Cost Dashboard page.
  Files in scope:   frontend/src/pages/costs.tsx (NEW — replaces placeholder)
                    frontend/src/App.tsx (MODIFY — update route from placeholder)
  Depends on:       TASK-02
  Required Tests:
    | Test ID          | Type | Pass Criteria                                      |
    |:-----------------|:-----|:---------------------------------------------------|
    | TEST-18-03-01    | unit | Cost dashboard renders without crashing            |
    | TEST-18-03-02    | unit | Shows total spend for today/week/all-time          |
    | TEST-18-03-03    | unit | Shows cost by provider breakdown                   |
    | TEST-18-03-04    | unit | Shows per-run cost list                             |
    | TEST-18-03-05    | unit | Shows budget utilization bar                        |
    | TEST-18-03-06    | unit | Handles API error gracefully                        |
  Acceptance Criteria:
    AC-03-01: User can see total cost at a glance
    AC-03-02: Costs broken down by provider, stage, and model
    AC-03-03: Budget limits are visualized

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Cost Dashboard shows complete cost breakdown
  BAC-02: CHANGELOG.md updated with BATCH-18 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-18/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:
Review Cycle:             [1 or 2]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS — list each Reviewer flag acted on:
  FLAG-01 → Action taken:

If REJECT — reason and next action:

Blueprint Version after response: [Increment if revised]
Lead Sign:                [Name + YYYY-MM-DD HH:MM]

═══════════════════════════════════════════════════════════
```

---

## BATCH-19: Memory Browser

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-19
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          [ASSIGNED]
Date Issued:              [YYYY-MM-DD]
Review SLA:               30 minutes
Execution SLA per Task:   90 minutes
Partial Sign-Off SLA:     15 minutes
Task Sequencing:          SEQUENTIAL

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Deliver a Memory Browser page allowing users to view, search, and delete
memories stored by the platform's memory system (working/episodic/semantic).

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Replace /memory placeholder with full Memory Browser page
  - Create API client for memory endpoints (6 endpoints exist)
  - Show memory statistics (total, by type)
  - Searchable/filterable memory list
  - Memory cards: content preview, type badge, confidence, date
  - Delete button per memory with confirmation
  - "Recall" search: query the memory system

What the code MUST NOT do:
  - Modify existing backend memory endpoints
  - Create new backend endpoints
  - Implement memory consolidation or management logic on frontend

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: No backend modifications. All memory endpoints already exist:
         GET /api/v1/memory/stats, GET /api/v1/memory/memories,
         GET /api/v1/memory/recall, DELETE /api/v1/memory/{id}

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Existing backend (backend/api/routes/memory.py):
  GET /memory/stats       → { total, by_type: {episodic: N, semantic: N, working: N} }
  GET /memory/memories    → MemoryEntry[] (paginated, filterable by type)
  GET /memory/recall?q=   → MemoryEntry[] (relevance-ranked)
  POST /memory/store      → { id } (not used in this Batch)
  DELETE /memory/{id}     → { deleted: true }
  GET /memory/types       → string[]

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: Memory deletion requires confirmation. No bulk delete.
  AR-02: Memory store endpoint is not exposed in this Batch's UI.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-16 (placeholder route)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,544 tests
  Expected delta (all Tasks):      +15 new tests
  Expected total at Batch close:   1,559

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-19/TASK-01 — Memory API Client & Components
  Description:      Create API client for memory endpoints and
                    MemoryCard/MemoryStats components.
  Files in scope:   frontend/src/api/memory.ts (NEW)
                    frontend/src/components/memory/memory-card.tsx (NEW)
                    frontend/src/components/memory/memory-stats.tsx (NEW)
  Depends on:       None
  Required Tests:
    | Test ID          | Type | Pass Criteria                                    |
    |:-----------------|:-----|:-------------------------------------------------|
    | TEST-19-01-01    | unit | getMemoryStats() calls correct endpoint           |
    | TEST-19-01-02    | unit | getMemories() accepts type filter param           |
    | TEST-19-01-03    | unit | recallMemories() sends query param                |
    | TEST-19-01-04    | unit | MemoryCard renders content, type badge, confidence|
    | TEST-19-01-05    | unit | MemoryCard delete button shows confirmation       |
    | TEST-19-01-06    | unit | MemoryStats renders total and per-type counts     |
  Acceptance Criteria:
    AC-01-01: All memory API functions typed correctly
    AC-01-02: MemoryCard shows content preview with type badge

TASK-02: BATCH-19/TASK-02 — Memory Browser Page
  Description:      Replace placeholder with full Memory Browser page.
  Files in scope:   frontend/src/pages/memory.tsx (NEW — replaces placeholder)
                    frontend/src/App.tsx (MODIFY — update route)
  Depends on:       TASK-01
  Required Tests:
    | Test ID          | Type | Pass Criteria                                      |
    |:-----------------|:-----|:---------------------------------------------------|
    | TEST-19-02-01    | unit | Memory page renders with stats header              |
    | TEST-19-02-02    | unit | Memory list renders with pagination                |
    | TEST-19-02-03    | unit | Type filter works (episodic/semantic/working)      |
    | TEST-19-02-04    | unit | Search input calls recall endpoint                 |
    | TEST-19-02-05    | unit | Delete confirmation removes memory from list       |
  Acceptance Criteria:
    AC-02-01: User can browse all stored memories
    AC-02-02: User can search memories by text query
    AC-02-03: User can delete individual memories with confirmation

TASK-03: BATCH-19/TASK-03 — Memory Page Integration
  Description:      Wire up the Memory Browser page to the sidebar
                    navigation and verify end-to-end flow.
  Files in scope:   frontend/src/components/layout/sidebar.tsx (MODIFY — update link)
  Depends on:       TASK-02
  Required Tests:
    | Test ID          | Type | Pass Criteria                                |
    |:-----------------|:-----|:---------------------------------------------|
    | TEST-19-03-01    | unit | Sidebar Memory link navigates to /memory     |
    | TEST-19-03-02    | integration | End-to-end: navigate → view stats → search → delete |
  Acceptance Criteria:
    AC-03-01: Memory Browser is fully accessible from sidebar

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Memory Browser shows all stored memories with search and filter
  BAC-02: CHANGELOG.md updated with BATCH-19 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-19/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:
Review Cycle:             [1 or 2]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS — list each Reviewer flag acted on:
  FLAG-01 → Action taken:

If REJECT — reason and next action:

Blueprint Version after response: [Increment if revised]
Lead Sign:                [Name + YYYY-MM-DD HH:MM]

═══════════════════════════════════════════════════════════
```

---

## Remaining Batches — Blueprint Summaries

> The Batches below follow the identical AIV Standard Cycle structure shown above.
> Full Blueprint templates will be expanded when each Batch is activated.
> This section provides enough detail for dependency planning and scope understanding.

---

### BATCH-20: Governance Queue
**Cycle:** STANDARD · **Tasks:** 2 · **Documents:** 8  
**Depends on:** BATCH-16  
**Goal:** Governance page with pending approvals, approve/deny with amendment.  
**Backend:** No changes (approve/deny endpoints already exist).  
**Frontend:** New governance.tsx page, approval-card component, API client.  
**HB-01:** No backend modifications. Governance endpoints already exist.

### BATCH-21: Observability / Traces Viewer
**Cycle:** STANDARD · **Tasks:** 3 · **Documents:** 10  
**Depends on:** BATCH-16  
**Goal:** Traces page with latency charts, trace list, span detail view.  
**Backend:** No changes (trace endpoints already exist).  
**Frontend:** New traces.tsx page, trace-detail component, latency chart, API client.  
**HB-01:** No backend modifications. Trace endpoints already exist.

### BATCH-22: Session Management UI
**Cycle:** STANDARD · **Tasks:** 3 · **Documents:** 10  
**Depends on:** BATCH-16  
**Goal:** Sessions page with create/manage/monitor. Pipeline form session selector.  
**Backend:** No changes (session lifecycle endpoints already exist).  
**Frontend:** New sessions.tsx page, session-card component, API client, pipeline form integration.  
**HB-01:** No backend modifications. Session endpoints already exist.

### BATCH-23: Literature Search UI
**Cycle:** STANDARD · **Tasks:** 2 · **Documents:** 8  
**Depends on:** BATCH-22  
**Goal:** Literature search page with multi-source search, paper cards, ingestion.  
**Backend:** NEW — backend/api/routes/literature.py (search endpoint).  
**Frontend:** New literature.tsx page, paper-card component, API client.  
**HB-01:** Literature search endpoint MUST be read-only for search. Ingestion is a separate action requiring user confirmation.

### BATCH-24: Knowledge Enhancement (Upload + Stats)
**Cycle:** STANDARD · **Tasks:** 2 · **Documents:** 8  
**Depends on:** BATCH-22  
**Goal:** PDF upload via drag-and-drop, enriched knowledge stats.  
**Backend:** NEW — POST /knowledge/ingest endpoint, enriched /knowledge/stats.  
**Frontend:** Upload zone component, stats banner on knowledge page.  
**HB-01:** Uploaded files MUST be validated as PDF before processing. No executable uploads.

---

═══════════════════════════════════════════════════════════════
# PHASE 3: INTELLIGENCE & AUTONOMY UX
═══════════════════════════════════════════════════════════════

### BATCH-25: Knowledge Graph Explorer
**Cycle:** STANDARD · **Tasks:** 4 · **Documents:** 12  
**Depends on:** BATCH-24  
**Goal:** Interactive knowledge graph visualization with entity detail, filtering, search.  
**Backend:** NEW — graph/stats, graph/entities, graph/entity/{id}, graph/subgraph endpoints.  
**Frontend:** New knowledge-graph.tsx page, graph-canvas (D3 force-directed), entity-detail panel.  
**HB-01:** Graph visualization MUST use client-side rendering only. No server-side image generation.  
**HB-02:** Initial render MUST be limited to 100 entities. Lazy-load on zoom/filter.

### BATCH-26: Autonomous Cycle Dashboard
**Cycle:** STANDARD · **Tasks:** 3 · **Documents:** 10  
**Depends on:** BATCH-25  
**Goal:** Autonomous dashboard with cycle monitoring, start/stop, consciousness state visualization, history.  
**Backend:** NEW — autonomous/status, autonomous/stop, autonomous/history endpoints.  
**Frontend:** New autonomous.tsx page, autonomous-form, cycle-progress component.  
**HB-01:** Autonomous stop endpoint MUST require confirmation. No silent termination.

### BATCH-27: Self-Improvement & Scheduler UI
**Cycle:** STANDARD · **Tasks:** 2 · **Documents:** 8  
**Depends on:** BATCH-26  
**Goal:** Self-improvement section in settings. Scheduler controls on autonomous page.  
**Backend:** NEW — status/evolution endpoint. Existing scheduler start/stop.  
**Frontend:** Self-improve section in settings, scheduler section on autonomous page.  
**HB-01:** Evolution parameters are READ-ONLY in the UI. No manual parameter editing.

---

═══════════════════════════════════════════════════════════════
# PHASE 4: PRODUCTION HARDENING
═══════════════════════════════════════════════════════════════

### BATCH-28: Authentication & Authorization
**Cycle:** STANDARD · **Tasks:** 3 · **Documents:** 10  
**Depends on:** BATCH-27  
**Goal:** JWT auth, User model, login page, role-based access.  
**Backend:** NEW — auth routes, User table, JWT middleware, role system.  
**Frontend:** Login page, auth context, protected routes.  
**HB-01:** All existing API endpoints MUST require authentication after this Batch.  
**HB-02:** Admin role MUST NOT be auto-assigned. First user is promoted manually.

### BATCH-29: Database Migration (Alembic)
**Cycle:** STANDARD · **Tasks:** 2 · **Documents:** 8  
**Depends on:** BATCH-28  
**Goal:** Alembic setup, initial migration, CLI commands.  
**Backend:** NEW — alembic.ini, migration env, initial migration. CLI: db upgrade/downgrade.  
**HB-01:** SQLite MUST still work for development. No PostgreSQL-only migration.

### BATCH-30: PostgreSQL & Docker Compose
**Cycle:** STANDARD · **Tasks:** 2 · **Documents:** 8  
**Depends on:** BATCH-28  
**Goal:** PostgreSQL support, Docker Compose for full stack.  
**Backend:** database.py PostgreSQL connection support. docker-compose.yml.  
**HB-01:** SQLite MUST still work. Dual compatibility is required.

### BATCH-31: SSE Auth & Responsive Design
**Cycle:** STANDARD · **Tasks:** 2 · **Documents:** 8  
**Depends on:** BATCH-29, BATCH-30  
**Goal:** SSE header-based auth. Mobile responsive layout.  
**Frontend:** Custom fetch-based SSE client, mobile sidebar → bottom nav, responsive grids.  
**HB-01:** API keys MUST NOT appear in URLs after this Batch.

### BATCH-32: Performance & Monitoring
**Cycle:** STANDARD · **Tasks:** 2 · **Documents:** 8  
**Depends on:** BATCH-31  
**Goal:** Dashboard lazy loading, gaps pagination, DB indexes, webhook notifications.  
**Backend:** Notification module (webhook), DB indexes, query optimization.  
**Frontend:** Lazy chart loading, pagination on gaps.  
**HB-01:** Dashboard MUST render in under 3 seconds with 1000+ ideas.

---

═══════════════════════════════════════════════════════════════
# PHASE 5: GROWTH & ECOSYSTEM
═══════════════════════════════════════════════════════════════

### BATCH-33: Export Enhancements & Plugin System
**Cycle:** STANDARD · **Tasks:** 3 · **Documents:** 10  
**Depends on:** BATCH-32  
**Goal:** PDF export, bulk export, plugin marketplace UI.  
**Backend:** PDF export via WeasyPrint, plugin registry endpoints.  
**Frontend:** Export enhancements, plugins page.

### BATCH-34: Collaboration & CLI Enhancement
**Cycle:** STANDARD · **Tasks:** 3 · **Documents:** 10  
**Depends on:** BATCH-32  
**Goal:** Comment threads, sharing, erock open/proposal/export commands.  
**Backend:** Comment and SharedIdea tables, collaboration routes.  
**Frontend:** Comment component, share dialog. CLI: open, proposal, export commands.

### BATCH-35: Documentation Site
**Cycle:** STANDARD · **Tasks:** 3 · **Documents:** 10  
**Depends on:** BATCH-33  
**Goal:** MkDocs documentation site with auto-deployment.  
**Files:** docs/ directory structure, mkdocs.yml, deployment config.

### BATCH-36: i18n Infrastructure
**Cycle:** SIMPLIFIED · **Tasks:** 1 · **Documents:** 3  
**Depends on:** BATCH-34  
**Goal:** Add react-i18next infrastructure. English as default.  
**Frontend:** i18next setup, translation files structure, LanguageSwitcher component.

### BATCH-37: World Model Viewer
**Cycle:** SIMPLIFIED · **Tasks:** 1 · **Documents:** 3  
**Depends on:** BATCH-34  
**Goal:** World model panel on knowledge graph page.  
**Backend:** NEW — knowledge/world-model endpoint.  
**Frontend:** World model panel component.

---

═══════════════════════════════════════════════════════════════
# APPENDIX A: DOCUMENT COUNT VERIFICATION
═══════════════════════════════════════════════════════════════

| Batch | Cycle | Tasks | Formula | Count |
|:---|:---|:---|:---|:---|
| BATCH-07 | SIMPLIFIED | 1 | 3 | 3 |
| BATCH-08 | SIMPLIFIED | 1 | 3 | 3 |
| BATCH-09 | SIMPLIFIED | 1 | 3 | 3 |
| BATCH-10 | STANDARD | 2 | 3 + (2×2) + 1 | 8 |
| BATCH-11 | STANDARD | 2 | 3 + (2×2) + 1 | 8 |
| BATCH-12 | STANDARD | 3 | 3 + (2×3) + 1 | 10 |
| BATCH-13 | STANDARD | 2 | 3 + (2×2) + 1 | 8 |
| BATCH-14 | STANDARD | 2 | 3 + (2×2) + 1 | 8 |
| BATCH-15 | STANDARD | 1 | 3 + (2×1) + 1 | 6 |
| BATCH-16 | STANDARD | 1 | 3 + (2×1) + 1 | 6 |
| BATCH-17 | SIMPLIFIED | 1 | 3 | 3 |
| BATCH-18 | STANDARD | 3 | 3 + (2×3) + 1 | 10 |
| BATCH-19 | STANDARD | 3 | 3 + (2×3) + 1 | 10 |
| BATCH-20 | STANDARD | 2 | 3 + (2×2) + 1 | 8 |
| BATCH-21 | STANDARD | 3 | 3 + (2×3) + 1 | 10 |
| BATCH-22 | STANDARD | 3 | 3 + (2×3) + 1 | 10 |
| BATCH-23 | STANDARD | 2 | 3 + (2×2) + 1 | 8 |
| BATCH-24 | STANDARD | 2 | 3 + (2×2) + 1 | 8 |
| BATCH-25 | STANDARD | 4 | 3 + (2×4) + 1 | 12 |
| BATCH-26 | STANDARD | 3 | 3 + (2×3) + 1 | 10 |
| BATCH-27 | STANDARD | 2 | 3 + (2×2) + 1 | 8 |
| BATCH-28 | STANDARD | 3 | 3 + (2×3) + 1 | 10 |
| BATCH-29 | STANDARD | 2 | 3 + (2×2) + 1 | 8 |
| BATCH-30 | STANDARD | 2 | 3 + (2×2) + 1 | 8 |
| BATCH-31 | STANDARD | 2 | 3 + (2×2) + 1 | 8 |
| BATCH-32 | STANDARD | 2 | 3 + (2×2) + 1 | 8 |
| BATCH-33 | STANDARD | 3 | 3 + (2×3) + 1 | 10 |
| BATCH-34 | STANDARD | 3 | 3 + (2×3) + 1 | 10 |
| BATCH-35 | STANDARD | 3 | 3 + (2×3) + 1 | 10 |
| BATCH-36 | SIMPLIFIED | 1 | 3 | 3 |
| BATCH-37 | SIMPLIFIED | 1 | 3 | 3 |

**Total AIV documents: 260**  
(Each document is a signed, archived artifact under `/docs/aiv/[BATCH-ID]/`)

═══════════════════════════════════════════════════════════════
# APPENDIX B: TEST COUNT TRAJECTORY
═══════════════════════════════════════════════════════════════

| After Batch | Backend Tests | Frontend Tests | Total |
|:---|:---|:---|:---|
| Baseline | 1,303 | 56 | 1,359 |
| BATCH-07 | 1,309 | 56 | 1,365 |
| BATCH-08 | 1,314 | 56 | 1,370 |
| BATCH-09 | 1,314 | 56 | 1,370 |
| BATCH-10 | 1,339 | 56 | 1,395 |
| BATCH-11 | 1,339 | 140 | 1,479 |
| BATCH-12 | 1,344 | 170 | 1,514 |
| BATCH-13 | 1,351 | 188 | 1,539 |
| BATCH-14 | 1,358 | 208 | 1,566 |
| BATCH-15 | 1,358 | 213 | 1,571 |
| BATCH-16 | 1,358 | 223 | 1,581 |
| BATCH-17 | 1,358 | 223 | 1,581 |
| BATCH-18 | 1,358 | 241 | 1,599 |
| BATCH-19 | 1,358 | 256 | 1,614 |
| BATCH-20 | 1,358 | 270 | 1,628 |
| BATCH-21 | 1,358 | 285 | 1,643 |
| BATCH-22 | 1,358 | 300 | 1,658 |
| BATCH-23 | 1,365 | 315 | 1,680 |
| BATCH-24 | 1,372 | 325 | 1,697 |
| BATCH-25 | 1,385 | 345 | 1,730 |
| BATCH-26 | 1,395 | 365 | 1,760 |
| BATCH-27 | 1,400 | 375 | 1,775 |
| BATCH-28 | 1,420 | 395 | 1,815 |
| BATCH-29 | 1,425 | 395 | 1,820 |
| BATCH-30 | 1,430 | 395 | 1,825 |
| BATCH-31 | 1,430 | 415 | 1,845 |
| BATCH-32 | 1,440 | 425 | 1,865 |
| BATCH-33 | 1,448 | 440 | 1,888 |
| BATCH-34 | 1,458 | 455 | 1,913 |
| BATCH-35 | 1,458 | 455 | 1,913 |
| BATCH-36 | 1,458 | 460 | 1,918 |
| BATCH-37 | 1,460 | 460 | 1,920 |

**Final projected total: ~1,920 tests** (+41% from baseline of 1,359)

═══════════════════════════════════════════════════════════════
# APPENDIX C: GIT COMMIT CONVENTION
═══════════════════════════════════════════════════════════════

Per AIV §8.3, every commit references Batch and Task:

```
feat(batch-07/task-01): add erock setup interactive wizard
docs(batch-09/task-01): rewrite README with quick start and architecture
feat(batch-10/task-01): annotate all API routes with descriptions and examples
fix(batch-10/task-02): standardize error responses and remove SystemExit
test(batch-11/task-01): add page tests for all 7 frontend pages
test(batch-11/task-02): add component tests for charts and markdown renderer
chore(batch-07): Batch Sign-Off Certificate
```

One commit per role action:
- **Lead:** Blueprint commit, Partial Sign-Off commit, Certificate commit
- **Assistant:** Implementation commit (code + tests)

Assistant commit body must include:
- Test evidence summary (N passed, M failed, K deferred)
- LOC delta
- Files changed count

═══════════════════════════════════════════════════════════════
# APPENDIX D: OPERATIONAL PRINCIPLES REMINDER
═══════════════════════════════════════════════════════════════

All Batches in this roadmap are governed by AIV v5.1 Operational Principles:

| # | Principle | Application to This Roadmap |
|:--|:---|:---|
| P1 | Specification accuracy is the Lead's quality lever | After each Batch, update module paths and field names in subsequent Blueprints based on Adaptations |
| P2 | Documents are truth; sessions are not | Gate on deliverable files and signed documents, never on session status |
| P3 | Reviewer catches gaps before they become errors | Recurring flags → fix this roadmap document, not dismiss the Reviewer |
| P4 | Simplified Cycle is a privilege | BATCH-07/08/09/17/36/37 qualify. All others are Standard. No misdeclaration. |
| P5 | Deferred tests are debts | Every deferred test has a tracking reference to a future Batch |
| P6 | Lead Override is an escape valve | Three consecutive overrides → halt and fix infrastructure |
| P7 | Hard Boundaries are contracts | A boundary affirmed CONFIRMED then violated → RETURN regardless of tests |
| P8 | Commit discipline is audit discipline | One commit per role action. No mixed commits. |
| P9 | LLM agents have no sense of time | Always compute timestamp deltas. Never rely on subjective perception. |

═══════════════════════════════════════════════════════════════

*End of Master Roadmap — Aligned to AIV Framework v5.1*  
*31 Batches · ~110 Tasks · ~260 Documents · ~1,920 Tests at Completion*  
*Determine cycle mode from Blueprint before applying any formula.*
