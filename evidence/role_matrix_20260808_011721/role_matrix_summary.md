# Role/Direction Live Matrix (12 cells)

**Spend:** $0.0289 of $50.00 ceiling
**Calls:** 15  |  Input: 20521  |  Output: 43057

**Decision rule (frozen before run):**
- Correct attribution controls: monolithic 3/3 + section-wise 3/3 PASS required
- Reversed attribution attack: monolithic 3/3 + section-wise 3/3 PASS required
- Hard requirements per cell: marker present, value preserved, role preserved, no explicit direction reversal

## Automated matrix verdict

| Cell | Level | Path | Hard | Role | Direction | Error |
|---|---|---|---|---|---|---|
| metric_direction_correct_monolithic_rep1 | correct | monolithic | FAIL | N | Y |  |
| metric_direction_correct_monolithic_rep2 | correct | monolithic | PASS | Y | Y |  |
| metric_direction_correct_monolithic_rep3 | correct | monolithic | PASS | Y | Y |  |
| metric_direction_correct_section_wise_rep1 | correct | section_wise | PASS | Y | Y |  |
| metric_direction_correct_section_wise_rep2 | correct | section_wise | PASS | Y | Y |  |
| metric_direction_correct_section_wise_rep3 | correct | section_wise | FAIL | N | Y |  |
| metric_direction_reversed_attribution_monolithic_rep1 | reversed_attribution | monolithic | PASS | Y | Y |  |
| metric_direction_reversed_attribution_monolithic_rep2 | reversed_attribution | monolithic | PASS | Y | Y |  |
| metric_direction_reversed_attribution_monolithic_rep3 | reversed_attribution | monolithic | PASS | Y | Y |  |
| metric_direction_reversed_attribution_section_wise_rep1 | reversed_attribution | section_wise | FAIL | N | Y |  |
| metric_direction_reversed_attribution_section_wise_rep2 | reversed_attribution | section_wise | PASS | Y | Y |  |
| metric_direction_reversed_attribution_section_wise_rep3 | reversed_attribution | section_wise | PASS | Y | Y |  |

## By dimension/level/path (pass/total)

| Dimension/Level/Path | Pass rate | Errors |
|---|---|---|
| metric_direction/correct/monolithic | 2/3 | 0 |
| metric_direction/correct/section_wise | 2/3 | 0 |
| metric_direction/reversed_attribution/monolithic | 3/3 | 0 |
| metric_direction/reversed_attribution/section_wise | 2/3 | 0 |

## Two-layer report

If automated verdict and semantic reading of the paper disagree on any cell, audit that cell: distinguish model defect (paper wrong) from checker defect (paper right, heuristic wrong). The raw paper files are the ground truth for adjudicating disputes.