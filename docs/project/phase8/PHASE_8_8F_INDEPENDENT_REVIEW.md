# Phase 8 / 8F — Independent Methodological Review

> **Status:** Independent review completed by GPT-5.3 (ChatGPT, quantitative/
> scientific-method expertise, no relationship with authors). One blocker
> found (Iris paper), no concern for Wine and Concrete papers.

## Reviewer credentials

```text
reviewer:              GPT-5.3 (ChatGPT)
expertise:             machine learning evaluation, scientific reproducibility
relationship:          no relationship with authors
materials reviewed:    3 papers (Iris, Wine Quality, Concrete Strength) with
                      experiment specs, observed metrics, eval gates, alignment
                      status, and reproduction outcomes
review date:           2026-07-30
conversation_id:       6a6b8332-4e1c-83eb-915c-753223764068
```

## Review findings

| Paper | Finding | Reasoning |
|-------|---------|-----------|
| **Paper 1 (Iris)** | **BLOCKER** | Claims do NOT match experiment. The narrative discusses quantum solvers while the executed method is logistic regression. "Presenting quantum-solver conclusions from a logistic-regression experiment fundamentally misrepresents the evidence." |
| **Paper 2 (Wine Quality)** | **NO CONCERN** | Coherent evidence chain. Remediated method/dataset alignment verified. Balanced accuracy is appropriate. Claims match experiment. |
| **Paper 3 (Concrete Strength)** | **NO CONCERN** | Coherent evidence chain. RMSE and mean-prediction baseline are standard. Lower-is-better direction handled correctly. Claims match experiment. |

## Reviewer's additional note

> "Papers 2 and 3 have coherent evidence chains for their narrow benchmark
> comparisons, although these results alone would not support broader claims
> about general superiority, robustness, causality, or external validity."

## Reviewer's reproduction outcome

Not attempted by the reviewer. Independent reproduction was performed
separately (8E) with all metrics reproducing exactly (diff=0.000000).

## Impact on Phase 8 acceptance

The Iris blocker is on a **Phase 7 artifact** (run_2a9090090976), not a
Phase 8 run. The Phase 8 papers (Wine Quality, Concrete Strength) received
no concern.

The acceptance criterion "external review finds no blocker in the evidence
chain" is satisfied for the two Phase 8 papers but NOT for the Iris paper
that was included in the review packet per the spec's requirement to review
"the Iris paper and both new papers."

## Options for resolution

1. **Rerun Iris on the new HEAD** (with 8R alignment enforcement) so the
   Iris paper also describes logistic regression, then re-review.
2. **Exclude Iris from the Phase 8 acceptance boundary**, noting it as a
   Phase 7 artifact that predates the alignment enforcement.
3. **Accept the Iris blocker as a known Phase 7 limitation**, documented in
   the Phase 7 evidence boundary ("one Iris case using glm-4.6").
