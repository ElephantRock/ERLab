# Phase 14 — Closeout Evidence

## 1. Experiment identity and cardinality

```text
ExperimentResult rows for phase14-rf-wine:  0 in DB (run in-process, ephemeral)
Experiment status:                          succeeded
model_family:                               random_forest (persisted in spec)
frozen hyperparameters:                     n_estimators=100, max_depth=10,
                                            min_samples_leaf=2, class_weight=balanced
random seed:                                42 (persisted in spec)
dataset hash:                               92dab01d21a5e8b5...
analysis-code hash:                         a67ef66c08bcb3d7...
feature_importance artifact hash:           06ad730e7f01c289...
artifact type:                              feature_importance (correctly typed)
```

No duplicate experiment row was created.

## 2. Independent reproduction

Two independent runs of the checked-in random-forest analysis:

```text
                              Run 1          Run 2          Diff        Tolerance
baseline_balanced_accuracy    0.500000       0.500000       0.00000000  0.001 PASS
baseline_accuracy             0.534375       0.534375       0.00000000  0.001 PASS
model_balanced_accuracy       0.791573       0.791573       0.00000000  0.001 PASS
model_accuracy                0.790625       0.790625       0.00000000  0.001 PASS
model_roc_auc                 0.880725       0.880725       0.00000000  0.001 PASS
top_feature_importance        0.224742       0.224742       0.00000000  0.001 PASS

feature_importance.csv hash:  06ad730e...    06ad730e...    IDENTICAL
analysis code hash:           a67ef66c...    a67ef66c...    IDENTICAL
```

All metrics and artifacts reproduce exactly (diff=0.00000000).

## 3. Artifact-to-claim audit

```text
Feature importance in paper:                 YES
Non-causal disclaimer present:               YES ("predictive contribution, not causal effect")
Causal overclaim patterns (caus, intervention, mechanism, effect of): NONE FOUND
RESULT markers in Methods section:           NONE (correct — markers only in Results/Conclusion)
RESULT markers in paper:                     [RESULT-1] through [RESULT-6] (all from deterministic blocks)
```

Feature-importance statement resolves to persisted artifact:
- Feature name: "alcohol" (from feature_importance.csv, top-ranked)
- Importance value: 0.224742 (from feature_importance.csv)
- Non-causal disclaimer: present in deterministic text
- RESULT marker: [RESULT-6]

No paper section describes feature importance as causal, intervention, mechanism, or proof.

## 4. Restart persistence

```text
Paper hash:     IDENTICAL post-restart
Spec hash:      IDENTICAL post-restart
model_family:   persists (random_forest)
hyperparameters: persist (n_estimators=100, max_depth=10, min_samples_leaf=2, class_weight=balanced)
```

## 5. Final repository verification

```text
Phase 13 typed-composition tests:    12 passed
Phase 12 evidence-bound tests:       10 passed
Phase 11 deterministic tests:        14 passed
Phase 10 controlled tests:           23 passed
Phase 9 controlled tests:            16 passed
Phase 8 claim alignment tests:        8 passed
Phase 8 controlled tests:            23 passed

Backend canonical selector:       5,033 passed, 0 failed
Frontend:                         988 passed, 0 failed
HEAD:                             c540069
Working tree:                     clean
```

## 6. External-review record

```text
reviewer:        GPT-5.3 (ChatGPT, model=auto)
conversation_id: 6a6c92b7-ae54-83ed-aefa-0470a8918c63
review date:     2026-07-31

Evidence supplied:
  - Title: "Random Forest on the Wine Quality Dataset"
  - Results: balanced_acc=0.792, accuracy=0.791, ROC-AUC=0.881
  - Feature importance: alcohol (0.225) with non-causal disclaimer
  - Conclusion: random forest outperformed baseline

Verbatim response:
  "no concern — The narrative matches the executed random-forest experiment,
   credits no unexecuted method, reports feature importance as predictive
   rather than causal, and contains no blocker."
```
