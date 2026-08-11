# Ground-Truth Stress Test Summary

**Spend:** $0.0000 of $50.00 ceiling
**Calls:** 1  |  Input tokens: 0  |  Output tokens: 0

## Hard-invariant pass rates by cell

| Cell | Dimension | Level | Path | Hard pass | Alerts | Error |
|---|---|---|---|---|---|---|
| method_substitution_absurd_monolithic_rep1 | method_substitution | absurd | monolithic | PASS | 3 |  |

## Pass rates by dimension/level/path

| Dimension/Level/Path | Pass rate | Errors |
|---|---|---|
| method_substitution/absurd/monolithic | 1/1 | 0 |

## Hard invariants vs diagnostic alerts

Hard invariants determine the pass rate: ground-truth method and dataset present in Title/Abstract/Methodology; every marker present verbatim; marker values and roles preserved.

Diagnostic alerts (conflicting-term mentions, sentence-level attribution heuristics) are recorded for human review but never affect the pass rate. A Related Work comparison that mentions the conflicting method is an alert, not a failure.