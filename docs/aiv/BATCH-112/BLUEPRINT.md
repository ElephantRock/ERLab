# BATCH-112 BLUEPRINT — ReferenceVerifier Pipeline Integration

**Batch ID:** BATCH-112  
**Blueprint Version:** 1.0  
**Cycle Mode:** STANDARD  
**Lead Programmer:** ivory-wolf  
**Date Issued:** 2026-05-07  
**Task Sequencing:** Sequential  

## BATCH GOAL

Wire the ReferenceVerifier into the orchestrator so it runs automatically
after proposal synthesis. Unverifiable citations are stripped and logged.

## SCOPE STATEMENT

### What the code MUST do:
- Add a `_verify_references()` method to PipelineOrchestrator
- Method runs after proposal_synthesis stage completes
- Passes corpus papers + proposal text to ReferenceVerifier
- Strips unverifiable citations from proposal sections when trust_score < 0.7
- Logs verification results (trust score, hallucinated count)

### What the code MUST NOT do:
- Must NOT block pipeline completion if verification fails (HB-01)
- Must NOT modify the gap analysis or idea generation stages
- Must NOT change the proposal synthesizer's prompt (already done in B111)

## HARD BOUNDARIES

- **HB-01:** Reference verification failure MUST NOT crash or halt the pipeline.
  It MUST log warnings and continue with stripped citations.
- **HB-02:** The verification step MUST run AFTER synthesis, never before.

## TEST BASELINE

| Metric | Value |
|:-------|:------|
| Baseline at Blueprint issuance | 2,244 |
| Expected delta | +8 |
| Expected total at Batch close | 2,252 |

## TASK LIST

### TASK-01: Wire ReferenceVerifier into Orchestrator Post-Synthesis

**Priority:** Critical  
**Description:** Add a `_verify_references()` method to PipelineOrchestrator that runs after proposal_synthesis. It calls ReferenceVerifier.verify() with the proposal text and corpus papers. If trust_score < 0.7, it strips citations via strip_unverified_citations(). Results are logged.

**Files in scope:**
- `backend/pipeline/orchestrator.py` (MODIFY)

**Depends on:** None

**Required Tests:**

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-112-01-01 | unit | _verify_references exists on orchestrator | Method missing | Remove method definition | assert hasattr(orchestrator, '_verify_references') |
| TEST-112-01-02 | unit | Verification runs without crashing on empty input | AttributeError on None | Pass None instead of proposal text | No exception raised |
| TEST-112-01-03 | unit | Verification logs warning on low trust score | Warning not emitted | Set trust_score to 0.3 | assert "trust" in caplog.text.lower() |
| TEST-112-01-04 | unit | Verification does not block pipeline (HB-01) | Pipeline halts | Raise exception in verifier | Pipeline continues, error logged |
| TEST-112-01-05 | unit | Verification accepts high trust score without modification | Citations incorrectly stripped | Set trust_score to 1.0 | Proposal sections unchanged |
| TEST-112-01-06 | unit | Corpus papers are passed as list of dicts | TypeError on Paper objects | Pass Paper objects instead of dicts | No TypeError |
| TEST-112-01-07 | unit | Verification runs after synthesis (HB-02) | Runs before synthesis | Mock synthesizer to fail | Verifier called after synthesizer |
| TEST-112-01-08 | unit | Stripped proposals still valid markdown | Malformed markdown output | Inject citations in headers | Headers preserved after strip |

**Acceptance Criteria:**
- AC-01: `_verify_references` method exists and is called after synthesis
- AC-02: Pipeline does not crash when verification fails (HB-01)
- AC-03: Unverifiable citations are replaced with `[Citation needed]` markers

**Traceability:**
- AC-01 → TEST-112-01-01, TEST-112-01-07
- AC-02 → TEST-112-01-02, TEST-112-01-04
- AC-03 → TEST-112-01-03, TEST-112-01-05

## BATCH-LEVEL ACCEPTANCE CRITERIA

- BAC-01: Reference verification wired into orchestrator
- BAC-02: All 8 tests pass
- BAC-03: CHANGELOG.md updated with BATCH-112 entry
- BAC-04: All documents archived under /docs/aiv/BATCH-112/
