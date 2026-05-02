BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-09
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
Rewrite README.md so a new user can understand the platform's purpose,
install it, configure it, and run their first research idea pipeline
within 5 minutes — referencing the new `erock setup` and `erock dev` commands.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - One-paragraph value proposition explaining what the platform does
  - 30-second quick start referencing `erock setup` and `erock dev`
  - Architecture overview section (ASCII or text diagram) showing the
    9-stage pipeline, multi-agent architecture, and knowledge graph
  - Interface guide covering CLI / Web UI / REST API
  - Configuration reference link (to .env.example or docs/)
  - Contributing guide section or link
  - Project status badge and version (v0.1.0)

What the code MUST NOT do:
  - Reference features that do not exist in the codebase
  - Include hardcoded API keys, secrets, or credentials
  - Duplicate the full API reference (link to /docs endpoint instead)

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Every CLI command and API endpoint referenced in the README
         MUST exist in the current codebase. No aspirational references.

  HB-02: The README MUST NOT contain any secret, token, or API key
         value — even placeholder values must use clearly marked
         examples like `sk-your-key-here`.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Current CLI commands (backend/cli/main.py):
  generate, batch-generate, search, ingest, export, stats,
  autonomous, config, health, setup (BATCH-07), dev (BATCH-08)

Current API base: http://localhost:8000
Swagger docs: http://localhost:8000/docs
Frontend: http://localhost:3000

Pipeline stages: knowledge_search → gap_identification → idea_generation →
  novelty_check → feasibility_scoring → synthesis → export → evaluation

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: The pyproject.toml project metadata (name, version, description)
         is the authority for project identity. README must match.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-07 (erock setup command — referenced in quick start)
  BATCH-08 (erock dev command — referenced in quick start)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,370 existing tests
  Expected delta (all Tasks):      +0 (documentation only)
  Expected total at Batch close:   1,370

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-09/TASK-01 — README Rewrite
  Description:      Complete rewrite of README.md covering value
                    proposition, quick start, architecture, interfaces,
                    and contribution guidelines.
  Files in scope:   README.md (REWRITE)
  Depends on:       None
  Required Tests:
    | Test ID          | Type   | Pass Criteria                                   |
    |:-----------------|:-------|:------------------------------------------------|
    | TEST-09-01-01    | manual | README quick start references `erock setup`     |
    | TEST-09-01-02    | manual | README mentions web UI and `erock dev`          |
    | TEST-09-01-03    | manual | Architecture section describes 9-stage pipeline |
    | TEST-09-01-04    | manual | All referenced CLI commands exist in main.py    |
    | TEST-09-01-05    | manual | All referenced API endpoints exist in routes/   |
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

Reviewer Report ID:       REVIEW-BATCH-09-2026-05-02
Review Cycle:             1
Lead Decision:            [x] ACCEPT WITH MODIFICATIONS

FLAG-01 (CHK-05): Not acted on — acceptance criteria verify content completeness.
  The 5-minute promise is a UX target, not a testable artifact.
FLAG-02 (CHK-09): Not acted on — BATCH-07 and BATCH-08 are APPROVED and closed
  (certificates at docs/aiv/BATCH-07/SIGN-OFF-CERTIFICATE.md and
  docs/aiv/BATCH-08/SIGN-OFF-CERTIFICATE.md).
FLAG-03 (CHK-13): Not acted on — TEST-09-01-01 through AC-04 collectively cover
  the scope. Additional manual tests would be redundant with acceptance criteria.
FLAG-04 (CHK-17): Acted on — added TEST-09-01-05 to verify all referenced API
  endpoints exist in the codebase.

Blueprint Version after response: 1.1
Lead Sign:                Lead + 2026-05-02 02:15

═══════════════════════════════════════════════════════════
