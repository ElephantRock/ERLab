BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-77
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-06
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          SEQUENTIAL

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Implement the fast_scan pipeline strategy: a 2-5 minute pipeline that
runs ingestion → gap analysis → ideation → light synthesis, skipping
tree search, novelty checking, and mechanical metrics.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - FastProposalSynthesizer produces 3-section proposals (Abstract, Key Idea, Method Sketch)
  - Each proposal < 3000 chars total
  - fast_scan strategy uses FastProposalSynthesizer instead of full ProposalSynthesizer
  - Results stored in same DB tables as deep_research
  - Pipeline completes in < 5 minutes (excluding network latency)

What the code MUST NOT do:
  - Must NOT modify deep_research strategy behavior
  - Must NOT create new database tables
  - Must NOT remove existing ProposalSynthesizer

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  python -m ruff check backend/ && python -m pytest --co -q

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: fast_scan MUST skip idea_generation (tree search), novelty_checking,
         and mechanical_metrics stages. These stages MUST NOT execute.
  HB-02: fast_scan proposals MUST be stored in the same proposals table
         with strategy: "fast_scan" metadata.
  HB-03: fast_scan MUST complete in < 5 minutes with standard configuration.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
  # New: backend/pipeline/synthesis/fast_synthesizer.py
  class FastProposalSynthesizer:
      """Produces abbreviated 3-section proposals for fast_scan strategy."""
      def __init__(self, provider: BaseLLMProvider)
      async def synthesize(self, ideas, gaps, papers) -> list[ResearchProposal]

  # New: backend/pipeline/synthesis/prompts/fast_synthesis_system.md
  # Prompt template for 3-section proposals

  # Modified: backend/pipeline/orchestrator.py
  # - In _build_stages() or run(), select FastProposalSynthesizer for fast_scan
  # - Wire via strategy config

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  - Fast scan results are labeled "Quick Scan" in the UI
  - Users prompted to run deep_research for full proposals

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  Depends on: BATCH-76 (strategy architecture)
  Required by: BATCH-81, BATCH-84

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists:       [x] YES
  Last Updated:            2026-05-06 (via BATCH-76 Close)
  Batches since update:    0
  Reconciliation audit:    [x] N/A

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,932 existing tests
  Expected delta (all Tasks):      +20 new tests
  Expected total at Batch close:   1,952

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-77/TASK-01 — Fast Proposal Synthesizer
  Priority:          Critical
  Description:       Create FastProposalSynthesizer with 3-section proposals.
  Files in scope:
    - backend/pipeline/synthesis/fast_synthesizer.py (NEW)
    - backend/pipeline/synthesis/prompts/fast_synthesis_system.md (NEW)
  Depends on:        None
  Required Tests:
    | Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
    |:--------|:-----|:------------------|:-------------|:-------------|:--------------|
    | TEST-77-01-01 | unit | synthesize returns list of ResearchProposal | Returns None on empty input | Call with empty lists, assert empty list | assert result == [] |
    | TEST-77-01-02 | unit | Each proposal has 3 sections | Missing section breaks rendering | Assert all 3 sections present | assert all(s in p.sections for s in ["Abstract","Key Idea","Method Sketch"]) |
    | TEST-77-01-03 | unit | Proposal text < 3000 chars | Long proposals slow UI | Assert len < 3000 | assert total_chars < 3000 |
    | TEST-77-01-04 | unit | Uses LLM provider correctly | Provider not called | Mock provider, assert called | assert mock_provider.complete.called |
    | TEST-77-01-05 | error | Handles LLM timeout gracefully | Timeout crashes pipeline | Raise TimeoutError, assert partial result | assert result contains fallback text |
  Acceptance Criteria:
    AC-01-01: FastProposalSynthesizer produces 3-section proposals
    AC-01-02: Each proposal < 3000 chars
    AC-01-03: Handles LLM timeout gracefully
  Traceability:
    AC-01-01 → TEST-77-01-02
    AC-01-02 → TEST-77-01-03
    AC-01-03 → TEST-77-01-05

TASK-02: BATCH-77/TASK-02 — Fast Scan Strategy Wiring
  Priority:          Critical
  Description:       Wire fast_scan strategy to use FastProposalSynthesizer
                     and verify stage execution.
  Files in scope:
    - backend/pipeline/orchestrator.py (MODIFY)
  Depends on:        TASK-01
  Required Tests:
    | Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
    |:--------|:-----|:------------------|:-------------|:-------------|:--------------|
    | TEST-77-02-01 | integration | fast_scan runs 6 enabled stages | Extra stages run | Check stage list | assert skipped stages not in list |
    | TEST-77-02-02 | integration | fast_scan does NOT run idea_generation | tree search runs | Assert not in list | assert "idea_generation" not executed |
    | TEST-77-02-03 | integration | fast_scan uses FastProposalSynthesizer | Uses wrong synthesizer | Check stage class | assert FastProposalSynthesizer used |
    | TEST-77-02-04 | unit | fast_scan persists results to same DB tables | Results lost | Query DB | assert results exist |
  Acceptance Criteria:
    AC-02-01: fast_scan runs 6 stages (no idea_generation, no novelty_checking, no mechanical_metrics)
    AC-02-02: fast_scan uses FastProposalSynthesizer
    AC-02-03: Results persisted to same DB tables
  Traceability:
    AC-02-01 → TEST-77-02-01, TEST-77-02-02
    AC-02-02 → TEST-77-02-03
    AC-02-03 → TEST-77-02-04

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: fast_scan pipeline produces 3-section proposals
  BAC-02: deep_research pipeline behavior unchanged
  BAC-03: CHANGELOG.md updated with BATCH-77 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-77/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Lead Override per §5.3 — implementing directly for infrastructure efficiency.

═══════════════════════════════════════════════════════════
