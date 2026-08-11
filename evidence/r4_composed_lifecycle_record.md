# R4 Strengthened Contract — Composed Lifecycle Acceptance Record

**Date:** 2026-08-10
**Lineage:** proposal 104 / experiment 66 / spec phase5-pilot-v1
**Commits:** dd3cb0c → 9cb5a52 → b8632cf → 7406a51

## Verdict: PASS

The composed lifecycle invariant is proven on one governed lineage:

```
corrupted P1 → numeric_fidelity BLOCK → autonomous remediation
→ clean P2-auto → numeric_fidelity PASS → freeze → release

RESULT TRUTH == RENDERED RESULT VALUES
    AND
E == F == R == H
```

## Lifecycle trace

```
P1 (rev 16):  hash=7b33cd41...  eval=blocked   source=pipeline
  ← LLM corrupted RESULT values (966667 instead of 0.966667, etc.)
  ← numeric_fidelity gate caught 5 corruptions live (1× RESULT-1, 1× RESULT-2, 3× RESULT-3)
  ← paper blocked; no freeze; no release

auto_revise_paper()
  ← derived repair directive from blocking findings
  ← one constrained LLM revision using persisted evidence
  ← evidence invariants verified (result markers, source map, manifest)
  ← re-evaluated all gates

P2-auto (rev 17):  hash=59ec7c08...  eval=ready   source=auto_remediation
  ← all gates pass
  ← zero numeric_fidelity mismatches
  ← promoted as canonical

freeze
  ← frozen as release-final

rev 18:  hash=59ec7c08...  eval=ready   source=release
  ← release body SHA256 == frozen hash
```

## Invariant verification

### RESULT TRUTH == RENDERED RESULT VALUES

Every numeric attribution beside every RESULT marker in the frozen
release-final equals its persisted observed_value:

```
0.966667 [RESULT-3]         truth=0.966667  ✅
0.333333 [RESULT-1]         truth=0.333333  ✅
0.633333 [RESULT-2]         truth=0.633333  ✅
**0.333333** [RESULT-1]     truth=0.333333  ✅
**0.966667** [RESULT-3]     truth=0.966667  ✅
**0.633333** [RESULT-2]     truth=0.633333  ✅
0.966667 [RESULT-3]         truth=0.966667  ✅
**0.333333** [RESULT-1]     truth=0.333333  ✅
**0.633333** [RESULT-2]     truth=0.633333  ✅
```

numeric_fidelity mismatches: **0**

### E == F == R == H

```
E = eval.paper_hash         = 59ec7c08f14b469600b8c9a66fd8da62b71642b507c347b300762c2e66941c75
F = frozen revision hash    = 59ec7c08f14b469600b8c9a66fd8da62b71642b507c347b300762c2e66941c75
R = SHA256(release body)    = 59ec7c08f14b469600b8c9a66fd8da62b71642b507c347b300762c2e66941c75
H = X-ERLab-Paper-Hash      = 59ec7c08f14b469600b8c9a66fd8da62b71642b507c347b300762c2e66941c75

E == F == R == H            ✅
```

### All gates on P2-auto

```
provenance               PASS  (30 mapped sources)
scope_alignment          PASS  (on_scope)
conclusion_support       PASS  (supported_by_paper)
experiment_alignment     PASS  (non-vacuous)
claim_result_alignment   PASS  (role + numeric)
numeric_fidelity         PASS  (0 mismatches)
```

### Pipeline reliability (from the live run that produced P1)

```
stages executed:         17
skipped_by_strategy:      1  (trimmer)
skipped_by_error:         0
```

## What this proves

ERLab generated a paper with corrupted empirical numbers. The
numeric-fidelity gate detected it, blocked release, and triggered
autonomous remediation. The remediator corrected the values using
persisted evidence authority, re-evaluated the exact successor under
all gates, and the corrected paper passed. Only then was it frozen
and released.

The released bytes are proven identical to the evaluated bytes, and
every RESULT value in those bytes matches the persisted experimental
truth.

## Separate tracking

The generation-side decimal-loss bug (LLM drops leading `0.` during
prose rewrite) remains open as a synthesis-quality defect. The
assurance layer demonstrably catches it regardless of where it
originates.

## Appendix: exact-version evaluation and freeze persistence contracts

Two additional contracts were closed after the composed lifecycle
was first proven.

### Contract 1: canonical P2 full-evaluation hash binding

**Defect found and fixed (commit 4c74809):** The repair endpoint's
post-remediation `_evaluate_paper()` call did not wire
`metadata["full_paper"]` (paper_markdown + source_map) or
`ctx.result.result_markers` into the evaluation context. Without
these, the evaluator returned `status: unavailable` and the
`paper_evaluation.paper_hash` remained stale (still P1's hash).

**Fix:** The repair endpoint now sets `full_paper` from the promoted
paper content and passes `result_markers` through the pipeline
result context, matching the pipeline's own evaluation path.

**Verification (fresh session, no manual commit):**
```
paper_md SHA256 == eval.paper_hash == 59ec7c08...
eval.status == ready
all gates PASS (provenance, scope, conclusion, experiment_alignment, numeric_fidelity)
```

### Contract 2: freeze persistence through real API transaction

The real freeze API route (`POST /api/v1/ideas/{id}/paper/freeze`)
calls `session.commit()` after `freeze_current_paper()` (ideas.py:572).
Called via HTTP against the running server, it returned:

```json
{"state": "frozen", "frozen_revision_id": 18, "frozen_paper_hash": "59ec7c08..."}
```

Verified in a completely fresh Python process / fresh DB session:
the frozen revision exists with the correct hash, no manual commit
needed.

### Final fresh-session verification

```
frozen revision persisted:     ✅ (id=18, source=release)
T == P (truth == rendered):     ✅ (0 numeric mismatches)
E == F == R == H:               ✅ (59ec7c08...)
eval.status == ready:           ✅

BOTH CONTRACTS: ✅ PASS
```
