BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-07
Blueprint Version:        1.1
Cycle Mode:               STANDARD
Lead Programmer:          Lead
Date Issued:              2026-05-01
Review SLA:               30 minutes
Execution SLA per Task:   60 minutes
Partial Sign-Off SLA:     15 minutes
Task Sequencing:          SEQUENTIAL (single task)

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Deliver an interactive `erock setup` CLI wizard that takes a new user
from zero configuration to a validated `.env` file and a successful
test pipeline run in under 5 minutes.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Interactive Python CLI wizard using `click` prompts (already a dependency)
  - Detect Python version (≥3.11 required)
  - Offer provider selection: OpenAI / Anthropic / Gemini / Ollama
  - Validate API keys against the chosen provider's health endpoint
  - Detect Ollama at localhost:11434 if selected
  - Write a complete `.env` file with all required variables
  - Optionally run a single-idea test pipeline to confirm end-to-end flow
  - Print next-steps URL for web UI

What the code MUST NOT do:
  - Require the user to manually edit `.env` after the wizard completes
  - Attempt to install Python or package dependencies
  - Modify any file other than the two declared in scope

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: The modification to backend/cli/main.py MUST NOT exceed 3 lines
         added (import + registration + blank line). No other changes
         to that file are permitted.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Current CLI registration (backend/cli/main.py):
  Uses Click group with @cli.command() decorators.
  Commands are registered by importing their module and adding to the group.

Required .env variables (from backend/config.py — Settings class):
  LLM_PROVIDER, OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY,
  OLLAMA_BASE_URL, LLM_MODEL, EMBEDDING_PROVIDER, EMBEDDING_MODEL,
  DATABASE_URL, CHROMA_PERSIST_DIR, CHROMA_COLLECTION_NAME,
  LOG_LEVEL, MAX_IDEAS_PER_ROUND, MAX_GAPS_PER_ROUND,
  NOVELTY_THRESHOLD, FEASIBILITY_THRESHOLD, EXPORT_FORMAT,
  COST_TRACKING_ENABLED

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: The Settings class in backend/config.py is the authority for
         which environment variables are required. The wizard must
         generate a .env matching every field in Settings.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  None — this Batch has no dependency on prior Batches.

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,359 existing tests
  Expected delta (all Tasks):      +6 new tests
  Expected total at Batch close:   1,365

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-07/TASK-01 — Setup Wizard CLI Command
  Description:      Create the `erock setup` interactive CLI command
                    as a new module with wizard flow, provider detection,
                    API key validation, `.env` generation, and optional
                    test pipeline execution. Register it in the CLI main.
  Files in scope:   backend/cli/commands/setup.py (NEW)
                    backend/cli/main.py (MODIFY — add import + command registration)
  Depends on:       None
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
Reviewer Report ID:       REVIEW-BATCH-07-2026-05-01
Review Cycle:             1
Lead Decision:            [x] ACCEPT WITH MODIFICATIONS

FLAG-01 → CHK-00 (CYCLE MODE): Correct flag. backend/cli/main.py is an existing
  source file being modified, which disqualifies SIMPLIFIED. Cycle mode upgraded
  to STANDARD. Hard Boundary HB-01 added to constrain the modification to 3 lines.
  Additional mandatory sections added (Data Models, Authority Rules, Dependency Map,
  Test Baseline) per STANDARD requirements.

Blueprint Version after response: 1.1
Lead Sign:                Lead + 2026-05-02 01:40

═══════════════════════════════════════════════════════════
