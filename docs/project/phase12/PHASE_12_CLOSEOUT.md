# Phase 12 — First-Pass Evidence-Bound Synthesis: Closeout

> **Status:** Phase 12 acceptance NOT MET. The evidence-bound approach
> resolved the title and experiment-alignment defects that persisted through
> Phases 9-11, but the RESULT-marker attribution problem persists in first-pass
> LLM output even with evidence-bound context.

## What Phase 12 achieved

```text
Title correctness              SOLVED (all 3 papers have correct titles)
Experiment alignment           SOLVED (all 3 pass with no_concern)
Scope alignment                SOLVED (all 3 on_scope)
Proposal-dominance             SOLVED (evidence-bound context is primary)
RESULT-marker attribution      NOT SOLVED (LLM cites baseline markers in model claims)
```

## The persistent boundary

The LLM (glm-4.6) consistently writes sentences like "the model achieved [RESULT-1]" where RESULT-1 is the baseline metric. This happens even when:
- The correct markers are provided in the prompt
- The deterministic Results section uses correct markers
- Abstract constraints explicitly say which method is executed

The root cause: the LLM generates abstract and conclusion prose that references markers by proximity, not by semantic correctness. It picks the first available marker (RESULT-1) rather than the correct one (RESULT-3).

## Phase record

```text
Phase 12      CLOSED — acceptance not met

Outcome:
  EVIDENCE_BOUND_TITLE_SYNTHESIS_PROVEN
  EXPERIMENT_ALIGNMENT_FIRST_PASS_SOLVED
  RESULT_ATTRIBUTION_FIRST_PASS_INSUFFICIENT
```

## All phases

```text
Phases 0–8    CLOSED — acceptance met
Phase 9       CLOSED — not met (REMEDIATION_MECHANISM_PROVEN)
Phase 10      CLOSED — not met (TARGETED_REPAIR_MECHANISM_PROVEN)
Phase 11      CLOSED — MET (DETERMINISTIC_FINALIZATION_PROVEN)
Phase 12      CLOSED — not met (TITLE_ALIGNMENT_SOLVED, RESULT_ATTRIBUTION_NOT_SOLVED)
```

The supported capability from Phase 12:

> ERLab can generate first-pass papers with correct titles and experiment
> alignment directly from persisted evidence, but the LLM may still
> misattribute RESULT markers in the abstract and conclusion, requiring
> the Phase 11 deterministic finalizer to correct the attribution.
