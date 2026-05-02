BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-13
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
Expose all backend pipeline options in the frontend form and enhance
the settings page with backend connectivity check, version display,
and default domain persistence.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add generation_rounds, export_format to pipeline form
  - Add toggle switches for run_novelty, run_feasibility, run_synthesis
  - Collapsible "Advanced Options" section
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
Backend config (backend/config.py — verified):
  generation_rounds: int = 2 (range 1-10)
  export_format: str = "markdown" (markdown|latex — no "none" option)
  run_novelty: bool = True
  run_feasibility: bool = True
  run_synthesis: bool = True
  max_gaps: not in config.py; API schema default = 5, range 1-20

PipelineRun.config_json stores these values per-run.

Frontend form (frontend/src/components/pipeline/run-config-form.tsx):
  Currently has: domain, max_ideas, max_gaps (wrong range 1-50)
  Missing: generation_rounds, export_format, run_novelty, run_feasibility, run_synthesis

Frontend API types (frontend/src/api/types.ts):
  PipelineRunRequest already has all fields defined but unused in the form.

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: Default values come from GET /api/v1/settings (backend config).
         localStorage defaults are fallback only.
  AR-02: Default domain is a frontend-only concern stored in localStorage.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-12 (pipeline page structure from results flow work)
  BATCH-12 status: APPROVED and closed (CERT-BATCH-12-2026-05-02)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,612 tests (1,512 backend + 100 frontend)
  Expected delta (all Tasks):      +13 new tests (1 backend + 12 frontend)
  Expected total at Batch close:   1,625

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
    AC-01-01: All backend pipeline options exposed in the form
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
    | TEST-13-02-04    | unit | Version display shows backend version from /status/detailed |
    | TEST-13-02-05    | unit | Default domain saved to localStorage                  |
    | TEST-13-02-06    | unit | Default domain loaded from localStorage on mount      |
    | TEST-13-02-07    | integration | GET /status/detailed returns version + provider  |
    | TEST-13-02-08    | unit | Settings page calls /status/detailed on mount for version |
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

Reviewer Report ID:       REVIEW-BATCH-13-2026-05-02
Review Cycle:             1
Lead Decision:            [x] ACCEPT WITH MODIFICATIONS

FLAG-01 (CHK-07): Acted on — Data Models corrected:
  generation_rounds default = 2 (not 3), max_gaps default = 5 (not 10),
  export_format = markdown|latex (no "none"), type name = PipelineRunRequest
  (not PipelineConfig).
FLAG-02 (CHK-13): Acted on — added TEST-13-02-08 verifying settings page
  calls /status/detailed on mount for version data. Clarified TEST-13-02-04
  to specify data source.
FLAG-03 (CHK-14): Acted on — corrected split to 1 backend + 12 frontend.
FLAG-04 (CHK-17): Acted on — same fixes as CHK-07 and CHK-14.

Blueprint Version after response: 1.1
Lead Sign:                Lead + 2026-05-02 03:55

═══════════════════════════════════════════════════════════
