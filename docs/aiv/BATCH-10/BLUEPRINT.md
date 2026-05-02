BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-10
Blueprint Version:        1.0
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
Annotate all 38 API endpoints with descriptions, examples, and response schemas,
and standardize all error responses to a single JSON format with remediation hints.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add `summary` and `description` to every FastAPI route decorator
  - Add `response_model` to endpoints missing it
  - Add example request/response in route docstrings
  - Document all error response codes (400, 401, 404, 422, 500)
  - Standardize error format to {"error": {"code": "...", "message": "..."}}
  - Replace all SystemExit calls in provider_factory.py with APIError
  - Add X-Request-Id (UUID4) header to all error responses
  - Create docs/api-guide.md with curl examples

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
  {"error": {"code": "string", "message": "string", "hint": "string (optional remediation)"}}
  Headers: X-Request-Id: <uuid4>

Route files and endpoint counts:
  backend/api/routes/pipeline.py    — 8 endpoints
  backend/api/routes/ideas.py       — 4 endpoints
  backend/api/routes/gaps.py        — 3 endpoints
  backend/api/routes/knowledge.py   — 4 endpoints
  backend/api/routes/status.py      — 2 endpoints
  backend/api/routes/memory.py      — 6 endpoints
  backend/api/routes/governance.py  — 4 endpoints
  backend/api/routes/costs.py       — 3 endpoints
  backend/api/routes/traces.py      — 4 endpoints
  Total: 38 endpoints

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
  Baseline at Blueprint issuance:  1,370 existing tests
  Expected delta (all Tasks):      +12 new tests
  Expected total at Batch close:   1,382

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-10/TASK-01 — API Route Annotation
  Description:      Add summary, description, response_model, and example
                    docstrings to all 38 FastAPI route handlers across
                    9 route modules. Create docs/api-guide.md.
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
    AC-02-04: 401 errors include a remediation hint

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

Reviewer Report ID:       REVIEW-BATCH-10-2026-05-02
Review Cycle:             1
Lead Decision:            [x] ACCEPT WITH MODIFICATIONS

FLAG-01 (CHK-03): Not acted on — API annotation and error standardization are
  two facets of a single deployable outcome (a documented, consistent API).
FLAG-02 (CHK-13): Not acted on — TEST-10-01-01 verifies OpenAPI schema completeness
  which implicitly covers response_model presence.
FLAG-03 (CHK-14): Acted on — Test baseline corrected from +25 to +12.
  Expected total at Batch close: 1,382 (not 1,395).
FLAG-04 (CHK-17): Acted on — Error response schema updated to include
  "hint" field: {"error": {"code": "...", "message": "...", "hint": "..."}}

Blueprint Version after response: 1.1
Lead Sign:                Lead + 2026-05-02 02:30

═══════════════════════════════════════════════════════════
