# Phase 6 / 6A — Recovery Baseline (Frozen)

> One immutable proposal–experiment pair is frozen as the only Phase 6 live target.

## Selection rule

Earliest successfully persisted `ExperimentResult` associated with the Phase 5
live run (`run_2718873e9191`), with `manifest_json IS NOT NULL AND success = 1`.

## Frozen target

```text
run_id:                  run_2718873e9191
experiment_result_id:    4
experiment_spec_id:      phase5-pilot-v1
proposal_id:             47 (idea 65: "Dynamic Graph Neural Networks for Telecom Customer Churn Prediction")
idea_id:                 65
```

## Frozen hashes

```text
dataset raw SHA-256:           1091a0dfd033acb7733af503637b2c7db8818ebe67ec8ccd5a4d4d5e57f5914f
analysis code SHA-256:         af0cd60565e1a3ce19e2cd07b8f2c06c4c8a880554e44004c8a05cc78aa66052
proposal content_md SHA-256:   21f9089a8ff6d101 (truncated to 16 hex for readability)
metrics.json SHA-256:          212a34a3fac2cd5d89a4d428fe127ba4b6ab9a9ce47733b26493c4b4f366664a
predictions.csv SHA-256:       3a3990c8f7ccad97f873c8724f2c67950ed729e5fec9417a1d361e5c7daaa77e
results_table.csv SHA-256:     c3d8f5215769e2cded9c55b087103797f41d187fcb3928bcb304a195518a2f79
literature source-map hash:    N/A (no paper was produced in Phase 5; no source markers exist)
```

## Frozen metrics (from persisted ExperimentManifest)

```text
baseline_accuracy:   0.333333
model_accuracy:      0.966667
improvement:         0.633333
random_seed:         42
split:               0.8/0.2 (120 train / 30 test)
```

## Experiment specification

```text
spec_id:              phase5-pilot-v1
dataset:              iris (v1.0.0, public domain)
analysis entrypoint:  experiments/phase5_pilot_v1/analysis.py
method:               multinomial logistic regression (one-vs-rest) vs majority-class baseline
declared metrics:     baseline_accuracy, model_accuracy, improvement
tolerances:           baseline_accuracy=0.001, model_accuracy=0.001, improvement=0.002
```

## Invariants for recovery

Before paper synthesis, recovery must verify:
- experiment status is `succeeded`
- experiment_spec_id matches `phase5-pilot-v1`
- dataset SHA-256 matches `1091a0df...`
- analysis code SHA-256 matches `af0cd605...`
- metrics.json SHA-256 matches `212a34a3...`
- all declared metrics present and finite
- observed metrics exactly match: `{baseline_accuracy: 0.333333, model_accuracy: 0.966667, improvement: 0.633333}`

Any mismatch aborts recovery before provider calls.

---

*Frozen at 2026-07-30. This baseline does not change during Phase 6.*
