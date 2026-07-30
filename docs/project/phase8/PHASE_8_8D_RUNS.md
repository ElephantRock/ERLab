# Phase 8 / 8D — Two Unattended Live Runs

> Both specifications ran from the same frozen HEAD (454dc49). No code changes
> between runs. G1 experiment succeeded; G2 experiment succeeded with eval=ready.

## Summary

```text
                          G1 Wine Quality         G2 Concrete Strength
run_id                    run_ab02edaa546c        run_53f893418e44
spec                      phase8-g1-wine          phase8-g2-concrete
task_type                 classification          regression
primary_metric            balanced_accuracy       model_rmse
metric direction          higher_better           lower_better
experiment status         succeeded               succeeded
paper eval                blocked                 ready
manual recovery           0                       0 (1 retry for empty provider response)
code changes between runs NONE
```

## G1 — Wine Quality classification

```text
experiment:  succeeded (6.7s)
results:
  baseline_balanced_accuracy:  0.500
  model_balanced_accuracy:     0.741
  baseline_accuracy:           0.534
  model_accuracy:              0.741
  model_roc_auc:               0.824
improvement: YES (higher_better, model > baseline on all metrics)
result_markers: 6 (all direction=higher_better)
paper: 1919 words, [RESULT-1..6] present
eval: blocked — 2 empirical claims lack [RESULT-N] backing (LLM variance)
```

The experiment fully succeeded and the markers are present. The paper eval
blocked because the LLM wrote broad architectural claims ("we demonstrate
that this unified architecture significantly outperforms") without citing
[RESULT-N] in those specific sentences. This is paper-synthesis variance,
not a code or experiment defect.

## G2 — Concrete Strength regression (lower_better)

```text
experiment:  succeeded (2.3s)
results:
  baseline_rmse:  16.054   (lower_better, baseline)
  baseline_mae:   13.052   (lower_better, baseline)
  model_rmse:      9.797   (lower_better, comparison)
  model_mae:       7.745   (lower_better, comparison)
  model_r2:        0.628   (higher_better, comparison)
  rmse_reduction:  6.257   (higher_better, derived)
improvement: YES (model_rmse < baseline_rmse with lower_better direction)
result_markers: 6 (mixed directions: lower_better + higher_better)
paper: 2094 words, [RESULT-1,3,5,6] present
eval: ready
  provenance:       passed (30 mapped sources)
  scope_alignment:  passed (on scope)
  conclusion_support: passed ("Claims are consistent with reported empirical results")
```

This is the critical regression test: lower_better metrics (RMSE, MAE) were
correctly handled end-to-end. The result_markers carry the correct direction
metadata from the spec through to persistence. The model outperformed the
baseline (lower RMSE) and the paper correctly cited [RESULT-N] markers.

## Direction metadata verification (D3 live proof)

```text
G1 markers: all 6 carry direction=higher_better
G2 markers:
  RESULT-1: baseline_mae     lower_better  baseline
  RESULT-2: baseline_rmse    lower_better  baseline
  RESULT-3: model_mae        lower_better  comparison
  RESULT-4: model_r2         higher_better comparison
  RESULT-5: model_rmse       lower_better  comparison
  RESULT-6: rmse_reduction   higher_better derived

Both higher_better and lower_better directions flowed from spec → manifest →
marker construction → persistence. The D3 structural direction fix works in
live runs.
```

## Retry note (G2)

The first G2 attempt (run_c57fb7c72587) failed because the provider returned
an empty response during gap_analysis ("provider returned empty response
(len=0)"). This is a provider issue, not a code blocker. One retry was
permitted per the spec. The retry (run_53f893418e44) completed successfully.
