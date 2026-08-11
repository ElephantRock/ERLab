# Ground-Truth Stress Test Summary

**Spend:** $0.1895 of $50.00 ceiling
**Calls:** 48  |  Input tokens: 67523  |  Output tokens: 215486

## Hard-invariant pass rates by cell

| Cell | Dimension | Level | Path | Hard pass | Alerts | Error |
|---|---|---|---|---|---|---|
| ablation_context_only_monolithic_rep1 | ablation | context_only | monolithic | PASS | 1 |  |
| ablation_context_only_monolithic_rep2 | ablation | context_only | monolithic | PASS | 0 |  |
| ablation_context_only_monolithic_rep3 | ablation | context_only | monolithic | PASS | 0 |  |
| ablation_context_only_section_wise_rep1 | ablation | context_only | section_wise | PASS | 5 |  |
| ablation_context_only_section_wise_rep2 | ablation | context_only | section_wise | PASS | 5 |  |
| ablation_context_only_section_wise_rep3 | ablation | context_only | section_wise | PASS | 5 |  |
| ablation_full_monolithic_rep1 | ablation | full | monolithic | PASS | 3 |  |
| ablation_full_monolithic_rep2 | ablation | full | monolithic | PASS | 3 |  |
| ablation_full_monolithic_rep3 | ablation | full | monolithic | PASS | 3 |  |
| ablation_full_section_wise_rep1 | ablation | full | section_wise | PASS | 8 |  |
| ablation_full_section_wise_rep2 | ablation | full | section_wise | PASS | 8 |  |
| ablation_full_section_wise_rep3 | ablation | full | section_wise | PASS | 8 |  |
| ablation_markers_only_monolithic_rep1 | ablation | markers_only | monolithic | PASS | 8 |  |
| ablation_markers_only_monolithic_rep2 | ablation | markers_only | monolithic | FAIL | 8 |  |
| ablation_markers_only_monolithic_rep3 | ablation | markers_only | monolithic | FAIL | 8 |  |
| ablation_markers_only_section_wise_rep1 | ablation | markers_only | section_wise | FAIL | 8 |  |
| ablation_markers_only_section_wise_rep2 | ablation | markers_only | section_wise | FAIL | 8 |  |
| ablation_markers_only_section_wise_rep3 | ablation | markers_only | section_wise | FAIL | 8 |  |
| method_substitution_absurd_monolithic_rep1 | method_substitution | absurd | monolithic | PASS | 3 |  |
| method_substitution_absurd_monolithic_rep2 | method_substitution | absurd | monolithic | PASS | 3 |  |
| method_substitution_absurd_monolithic_rep3 | method_substitution | absurd | monolithic | PASS | 3 |  |
| method_substitution_absurd_section_wise_rep1 | method_substitution | absurd | section_wise | PASS | 8 |  |
| method_substitution_absurd_section_wise_rep2 | method_substitution | absurd | section_wise | PASS | 8 |  |
| method_substitution_absurd_section_wise_rep3 | method_substitution | absurd | section_wise | PASS | 8 |  |
| method_substitution_plausible_monolithic_rep1 | method_substitution | plausible | monolithic | PASS | 4 |  |
| method_substitution_plausible_monolithic_rep2 | method_substitution | plausible | monolithic | PASS | 4 |  |
| method_substitution_plausible_monolithic_rep3 | method_substitution | plausible | monolithic | PASS | 4 |  |
| method_substitution_plausible_section_wise_rep1 | method_substitution | plausible | section_wise | PASS | 5 |  |
| method_substitution_plausible_section_wise_rep2 | method_substitution | plausible | section_wise | PASS | 4 |  |
| method_substitution_plausible_section_wise_rep3 | method_substitution | plausible | section_wise | PASS | 5 |  |
| method_substitution_subtle_monolithic_rep1 | method_substitution | subtle | monolithic | PASS | 4 |  |
| method_substitution_subtle_monolithic_rep2 | method_substitution | subtle | monolithic | PASS | 4 |  |
| method_substitution_subtle_monolithic_rep3 | method_substitution | subtle | monolithic | PASS | 5 |  |
| method_substitution_subtle_section_wise_rep1 | method_substitution | subtle | section_wise | PASS | 6 |  |
| method_substitution_subtle_section_wise_rep2 | method_substitution | subtle | section_wise | PASS | 6 |  |
| method_substitution_subtle_section_wise_rep3 | method_substitution | subtle | section_wise | PASS | 5 |  |
| metric_direction_correct_monolithic_rep1 | metric_direction | correct | monolithic | PASS | 3 |  |
| metric_direction_correct_monolithic_rep2 | metric_direction | correct | monolithic | PASS | 3 |  |
| metric_direction_correct_monolithic_rep3 | metric_direction | correct | monolithic | PASS | 3 |  |
| metric_direction_correct_section_wise_rep1 | metric_direction | correct | section_wise | PASS | 3 |  |
| metric_direction_correct_section_wise_rep2 | metric_direction | correct | section_wise | PASS | 3 |  |
| metric_direction_correct_section_wise_rep3 | metric_direction | correct | section_wise | PASS | 3 |  |
| metric_direction_reversed_attribution_monolithic_rep1 | metric_direction | reversed_attribution | monolithic | PASS | 3 |  |
| metric_direction_reversed_attribution_monolithic_rep2 | metric_direction | reversed_attribution | monolithic | PASS | 3 |  |
| metric_direction_reversed_attribution_monolithic_rep3 | metric_direction | reversed_attribution | monolithic | PASS | 3 |  |
| metric_direction_reversed_attribution_section_wise_rep1 | metric_direction | reversed_attribution | section_wise | PASS | 3 |  |
| metric_direction_reversed_attribution_section_wise_rep2 | metric_direction | reversed_attribution | section_wise | PASS | 3 |  |
| metric_direction_reversed_attribution_section_wise_rep3 | metric_direction | reversed_attribution | section_wise | PASS | 3 |  |

## Pass rates by dimension/level/path

| Dimension/Level/Path | Pass rate | Errors |
|---|---|---|
| ablation/context_only/monolithic | 3/3 | 0 |
| ablation/context_only/section_wise | 3/3 | 0 |
| ablation/full/monolithic | 3/3 | 0 |
| ablation/full/section_wise | 3/3 | 0 |
| ablation/markers_only/monolithic | 1/3 | 0 |
| ablation/markers_only/section_wise | 0/3 | 0 |
| method_substitution/absurd/monolithic | 3/3 | 0 |
| method_substitution/absurd/section_wise | 3/3 | 0 |
| method_substitution/plausible/monolithic | 3/3 | 0 |
| method_substitution/plausible/section_wise | 3/3 | 0 |
| method_substitution/subtle/monolithic | 3/3 | 0 |
| method_substitution/subtle/section_wise | 3/3 | 0 |
| metric_direction/correct/monolithic | 3/3 | 0 |
| metric_direction/correct/section_wise | 3/3 | 0 |
| metric_direction/reversed_attribution/monolithic | 3/3 | 0 |
| metric_direction/reversed_attribution/section_wise | 3/3 | 0 |

## Hard invariants vs diagnostic alerts

Hard invariants determine the pass rate: ground-truth method and dataset present in Title/Abstract/Methodology; every marker present verbatim; marker values and roles preserved.

Diagnostic alerts (conflicting-term mentions, sentence-level attribution heuristics) are recorded for human review but never affect the pass rate. A Related Work comparison that mentions the conflicting method is an alert, not a failure.