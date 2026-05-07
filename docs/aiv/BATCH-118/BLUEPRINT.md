# BATCH-118 BLUEPRINT — Ideator Agent Prompt Hardening

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-118
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-07

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Harden the ideator agent prompt to produce more concrete ideas
with preliminary architecture sketches and measurable criteria.
Add citation integrity instructions.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add citation integrity instruction to ideator_system.md
  - Add instruction for concrete architecture components
  - Add instruction for measurable success criteria
  - Require ideas to specify expected failure modes

What the code MUST NOT do:
  - Must NOT change the IdeaCandidate data model
  - Must NOT change the tree search engine

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Prompt changes must not reduce idea generation rate

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  python -m pytest --co -q 2>&1 | tail -1

───────────────────────────────────────────────────────────
DATA MODELS
───────────────────────────────────────────────────────────
  File: backend/pipeline/generation/prompts/ideator_system.md (MODIFY)
  Must preserve {{ n_ideas }}, {{ context }}, {% if prior_critique %} template variables

───────────────────────────────────────────────────────────
STATE.md STATUS: [x] YES

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline: 2,288  Expected delta: +4  Expected total: 2,292

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: Harden Ideator System Prompt
  Priority:          High
  Files in scope: backend/pipeline/generation/prompts/ideator_system.md (MODIFY)
  Required Tests:
    | Test ID         | Type | Behavior Verified              | Failure Mode          | Falsified By               | Pass Criteria              |
    |:----------------|:-----|:-------------------------------|:----------------------|:---------------------------|:---------------------------|
    | TEST-118-01-01  | unit | Prompt contains citation integrity | Missing          | Remove text                | "citation" in prompt.lower() |
    | TEST-118-01-02  | unit | Prompt requires architecture   | Missing              | Remove section             | "architecture" or "component" in prompt.lower() |
    | TEST-118-01-03  | unit | Prompt requires failure modes  | Missing              | Remove section             | "failure" in prompt.lower() |
    | TEST-118-01-04  | unit | Template has n_ideas variable  | Template broken      | Remove variable            | "n_ideas" in prompt        |
  Acceptance Criteria:
    AC-01: Prompt contains citation integrity instructions
    AC-02: Prompt requires architecture, failure modes, measurable criteria
    AC-03: Template variables preserved
  Traceability:
    AC-01 → TEST-118-01-01
    AC-02 → TEST-118-01-02, TEST-118-01-03
    AC-03 → TEST-118-01-04

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Ideator prompt hardened
  BAC-02: All 4 tests pass
  BAC-03: CHANGELOG.md updated
  BAC-04: Documents archived under /docs/aiv/BATCH-118/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Reviewer Report ID: REVIEW-BATCH-118-2026-05-07
Review Cycle: 1
Lead Decision: [x] ACCEPT
2 flags (stale baseline). Accepted.
Lead Sign: ivory-wolf — 2026-05-07

═══════════════════════════════════════════════════════════
```
