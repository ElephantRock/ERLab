# Productive-1 P1-13 adjudication — mechanical, per the frozen contract

## Verdict: FAIL — the candidate closes

Frozen criterion: ≥7/8 overall AND ≥3/4 per capability family AND zero
unsupported-numeric negative-control promotions AND zero operator
edits/continuation decisions AND unchanged assurance semantics AND
ordinary release identity on every successful trial.

Achieved: **6/8 overall; calibration 4/4; regression 2/4.** Negative
control blocked (percentage scaling rejected by the unchanged
validator). Zero operator edits or continuation decisions mid-trial.
No assurance semantics changed. Per the frozen rule the candidate is
closed: no second repair, no gate loosening, failure preserved.

## Trial results

| Trial | Family | Result |
| --- | --- | --- |
| calib-A#1 | calibration | promoted, ready, 0 numeric mismatches, E==F==R==H ✓ |
| calib-A#2 | calibration | promoted, ready, 0 numeric mismatches, E==F==R==H ✓ |
| calib-B#1 | calibration | promoted, ready, 0 numeric mismatches, E==F==R==H ✓ |
| calib-B#2 | calibration | promoted, ready, 0 numeric mismatches, E==F==R==H ✓ |
| regr-A#1 | regression | promoted, ready, 0 numeric mismatches, E==F==R==H ✓ |
| regr-A#2 | regression | promoted, ready, 0 numeric mismatches, E==F==R==H ✓ |
| regr-B#1 | regression | NOT promoted; revision carries 2 defective markers (RESULT-26, RESULT-53), each rendered 3× with the same wrong value (0.006701, 0.012442); the repair fixed 4 of the original 6 defects |
| regr-B#2 | regression | numeric SUCCESS (0 mismatches; revision persisted ready and promoted) but the route's post-repair re-evaluation returned blocked on conclusion_support ("empirical claim 'results show that' without [RESULT-N] backing") — no freeze |

## Miss attribution

- **regr-B#1 — model numeric failure** (the frozen close condition):
  with six structured targets and multi-render markers, the single
  revision left two targets wrong and repeated each wrong value across
  three renderings.
- **regr-B#2 — evaluation-consistency divergence, OUT of Productive-1
  scope:** the remediator's internal gate evaluation returned ready
  (revision persisted ready, promoted=true) while the route's
  re-evaluation of the same revised paper returned blocked on a SEMANTIC
  gate (conclusion_support). Productive-1 changed nothing on that path
  (numeric targeting only; the same divergence shape is reachable on
  the unchanged baseline). Recorded as a NEW product observation for
  the owner: candidate defect — post-repair re-evaluation can disagree
  with the promotion decision on semantic gates.

## What the qualification did establish

The numeric-repair-targeting mechanism itself performed 7/8 trials
numerically clean (zero mismatches under the unchanged validator,
including regr-B#2) versus the unchanged path's demonstrated failure
shape (one-plus mismatch in every observed one-shot repair, P1-2 and
the Case-4 qualifying run). The frozen criterion was nonetheless
missed, and the mechanical rule governs: the candidate closes.
