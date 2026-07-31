# Phase 10 — Targeted Semantic Repair: Closeout

> ERLab implemented and live-tested one-attempt targeted section repair on the
> Phase 9 Iris and Wine cases. Both attempts improved the experiment narrative
> without rerunning research or changing evidence identities, but neither
> satisfied external review. The live validation exposed two internal false-ready
> defects: incompatible titles were omitted from repair targeting, and
> RESULT-marker existence was validated without confirming that the marker's
> metric and role supported the surrounding claim. Phase 10 acceptance was not met.

## Phase record

```text
Phase 10       CLOSED — acceptance not met

Outcome:
  TARGETED_SECTION_REPAIR_MECHANISM_PROVEN
  TARGET_DERIVATION_INCOMPLETE
  RESULT_CLAIM_SEMANTICS_INCOMPLETE
  SINGLE_PASS_RELIABILITY_INSUFFICIENT
```

## What was proven

- Section-targeted architecture works: only defective sections were regenerated
- Unaffected content preserved byte-for-byte
- Evidence maps remained unchanged
- No experiment or research stage reran
- Both provider responses improved central narratives
- Revision history preserved with audit trail

## What failed

- Iris and Wine revision-1 papers were promoted as false-ready
- Title "# Quantum Solver" was not flagged as a repair target
- Iris conclusion credited [RESULT-1] (baseline accuracy) to the model
- Internal gates passed but external review found blockers

## Corrections applied (no provider calls)

### A. Title in claim_alignment evaluation
Quantum title on a logistic-regression paper is now a blocker. The title is
checked alongside abstract, conclusion, and contributions.

### B. Claim-to-result semantic validation
New gate validates that RESULT markers cited in model-claims are comparison-role
markers, not baseline-role markers. "The model achieved [RESULT-1]" is blocked
when RESULT-1.role == baseline.

### C. Revision-1 outputs frozen
The false-ready revision-1 papers are preserved as regression fixtures with
their defects documented.

### D. Re-evaluation with hardened evaluator
Both papers correctly blocked after hardening:
- Iris: blocked (quantum title + wrong RESULT marker)
- Wine: blocked (quantum title)

### E. Demotion
Both revision-1 papers demoted from canonical. Revision 0 (original fixtures)
restored as canonical paper_md. Revision 1 stored as blocked in PaperRevision.

## All phases

```text
Phases 0–8    CLOSED — acceptance met
Phase 9       CLOSED — acceptance not met (REMEDIATION_MECHANISM_PROVEN)
Phase 10      CLOSED — acceptance not met (TARGETED_REPAIR_MECHANISM_PROVEN)
```
