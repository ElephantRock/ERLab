# BATCH-112 BLUEPRINT — ReferenceVerifier Pipeline Integration

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-112
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-07
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Wire the ReferenceVerifier into the orchestrator so it runs automatically
after proposal synthesis. Unverifiable citations are stripped and logged.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add a _verify_references() method to PipelineOrchestrator
  - Pass corpus papers + proposal text to ReferenceVerifier
  - Strip unverifiable citations from proposal sections
  - Log verification results (trust score, hallucinated count)

What the code MUST NOT do:
  - Must NOT block pipeline completion if verification fails (HB-01)
  - Must NOT modify the gap analysis or idea generation stages
  - Must NOT change the proposal synthesizer's prompt (already done in B111)

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  python -m pytest --co -q 2>&1 | tail -1

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Reference verification failure MUST NOT crash or halt the pipeline.
         It MUST log warnings and continue with stripped citations.
  HB-02: The verification step MUST run AFTER synthesis, never before.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
  PipelineOrchestrator (backend/pipeline/orchestrator.py):
    - __init__ creates self._reference_verifier = ReferenceVerifier()
    - _verify_references(self, result: PipelineResult, ctx: StageContext) -> None
    - Called inside `if stage.name == "proposal_synthesis"` block

  ReferenceVerifier (backend/pipeline/verification/reference_verifier.py):
    - verify(proposal_text: str, corpus_papers: list[dict]) -> VerificationReport
    - strip_unverified_citations(proposal_text: str, report: VerificationReport) -> str
    - VerificationReport has: trust_score (float), verified (int), unverifiable (int)

  PipelineResult (backend/pipeline/result.py):
    - proposals: dict[int, ResearchProposal]
    - ResearchProposal has: content_md (str), metadata (str/JSON)

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  None — this Batch adds non-blocking post-processing.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-111: ReferenceVerifier, ProposalDeepener, PipelineEvaluator modules created
  BATCH-75: _STAGE_ORDER established with 9 entries

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists:       [x] YES
  Last Updated:            2026-05-07
  Batches since update:    0 (BATCH-111 close)
  Reconciliation audit:    N/A (< 5 batches since update)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  2,244
  Expected delta:                  +8
  Expected total at Batch close:   2,252

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: Wire ReferenceVerifier into Orchestrator Post-Synthesis
  Priority:          Critical
  Description:       Add a _verify_references() method to PipelineOrchestrator
                     that runs after proposal_synthesis. It calls
                     ReferenceVerifier.verify() with the proposal text and
                     corpus papers. If trust_score < 0.7, it strips citations
                     via strip_unverified_citations(). Results are logged.
  Files in scope:
    - backend/pipeline/orchestrator.py (MODIFY — add _verify_references method,
      add ReferenceVerifier import, add self._reference_verifier to __init__,
      add call inside proposal_synthesis persistence block)
  Depends on:        None
  Required Tests:
    | Test ID            | Type | Behavior Verified                    | Failure Mode                  | Falsified By                          | Pass Criteria                        |
    |:-------------------|:-----|:-------------------------------------|:------------------------------|:--------------------------------------|:-------------------------------------|
    | TEST-112-01-01     | unit | _verify_references exists on orchestrator | Method missing | Remove method definition | assert hasattr(orchestrator, '_verify_references') |
    | TEST-112-01-02     | unit | Verification runs without crashing on empty input | AttributeError on None | Pass None instead of proposal text | No exception raised |
    | TEST-112-01-03     | unit | Verification logs warning on low trust score | Warning not emitted | Set trust_score to 0.3 | assert "trust" in caplog.text.lower() |
    | TEST-112-01-04     | unit | Verification does not block pipeline (HB-01) | Pipeline halts | Raise exception in verifier | Pipeline continues, error logged |
    | TEST-112-01-05     | unit | Verification accepts high trust score without modification | Citations incorrectly stripped | Set trust_score to 1.0 | Proposal sections unchanged |
    | TEST-112-01-06     | unit | Corpus papers are passed as list of dicts | TypeError on Paper objects | Pass Paper objects instead of dicts | No TypeError |
    | TEST-112-01-07     | unit | Verification runs after synthesis (HB-02) | Runs before synthesis | Mock synthesizer to fail | Verifier called after synthesizer |
    | TEST-112-01-08     | unit | Stripped proposals still valid markdown | Malformed markdown output | Inject citations in headers | Headers preserved after strip |
  Acceptance Criteria:
    AC-01: _verify_references method exists and is called after synthesis
    AC-02: Pipeline does not crash when verification fails (HB-01)
    AC-03: Unverifiable citations are replaced with [Citation needed] markers
  Traceability:
    AC-01 → TEST-112-01-01, TEST-112-01-07
    AC-02 → TEST-112-01-02, TEST-112-01-04
    AC-03 → TEST-112-01-03, TEST-112-01-05

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Reference verification wired into orchestrator
  BAC-02: All 8 tests pass
  BAC-03: CHANGELOG.md updated with BATCH-112 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-112/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

Reviewer Report ID:       REVIEW-BATCH-112-2026-05-07
Review Cycle:             1
Lead Decision:            [x] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

Notes: Reviewer fallback per §4.5 — spawned session 260507-grand-topaz produced
non-compliant output (wrong template format). Lead wrote Review Report directly.
Fallback does not count as a Review Cycle.

Blueprint Version after response: 1.0 (no revision needed)
Lead Sign:                ivory-wolf — 2026-05-07

═══════════════════════════════════════════════════════════
```
