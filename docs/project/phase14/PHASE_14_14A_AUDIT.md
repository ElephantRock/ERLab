# Phase 14 / 14A — Linear-Model Assumption Audit

## Hard blockers for nonlinear methods

1. **claim_alignment.py:185-195** — `executed_terms` hardcoded to logistic/linear regression. A random-forest spec produces empty `executed_terms`, so the paper can never pass alignment. **This is the single most damaging blocker.**

2. **empirical_runner.py:232-234** — artifact type inferred by filename substring. `feature_importance.csv` → mislabeled as `"figure"`.

3. **specification.py** — no `model_family` or `hyperparameters` field. Preprocessing config silently dropped.

4. **deterministic_finalizer.py:63** — `render_result_claim(observed_value: float)` cannot render feature-importance claims.

5. **claim_alignment.py:197-203** — `baseline_terms` hardcoded to majority/mean.

## What's already model-agnostic

- `claim_result_validator.py` — operates on marker roles, not model family
- `direction_evaluator.py` — operates on metric direction, not model
- `typed_claim_composer.py` — method name parsed generically from `analysis_method` string
- Scalar metrics in metrics.json work fine for random forest (balanced_accuracy, accuracy, roc_auc)

## Required fixes

1. Generalize `executed_terms` detection to use the spec's method name
2. Add `"feature_importance"` artifact type recognition
3. Add `model_family` and `hyperparameters` to ExperimentSpec
4. Add feature-importance typed renderer
5. Generalize baseline_terms detection
