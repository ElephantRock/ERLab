# Phase 8 / 8D — G1 Wine Quality Live Run

> **Status:** G1 COMPLETED. Experiment succeeded. Paper eval BLOCKED (2 unbacked
> empirical claims — LLM variance, not code blocker).

## Run manifest

```text
run_id:                  run_ab02edaa546c
db_id:                   2521
domain:                  machine learning
strategy:                deep_research
experiment_spec_id:      phase8-g1-wine
HEAD:                    454dc49 (frozen for 8D)
started:                 2026-07-30 ~12:25
completed:               2026-07-30 ~13:19
status:                  completed
operator intervention:   NONE
code changes since G1:   NONE (frozen HEAD)
```

## Experiment result

```text
spec:                    phase8-g1-wine
status:                  succeeded
duration:                6.7s
results:
  baseline_balanced_accuracy:  0.500000
  baseline_accuracy:           0.534375
  baseline_roc_auc:            0.500000
  model_balanced_accuracy:     0.740904
  model_accuracy:              0.740625
  model_roc_auc:               0.824169
direction:               higher_better (all metrics)
improvement:             YES (model outperforms baseline on all metrics)
```

## Paper

```text
proposal_id:             54 (selected, feasibility=7.3)
word_count:              1919
synthesis_strategy:      monolithic
[RESULT-N] markers:      6 present (RESULT-1 through RESULT-6)
  RESULT-1 → baseline_accuracy=0.534375 (higher_better)
  RESULT-2 → baseline_balanced_accuracy=0.500000 (higher_better)
  RESULT-3 → baseline_roc_auc=0.500000 (higher_better)
  RESULT-4 → model_accuracy=0.740625 (higher_better)
  RESULT-5 → model_balanced_accuracy=0.740904 (higher_better)
  RESULT-6 → model_roc_auc=0.824169 (higher_better)
[SOURCE-N] markers:      present
source_map:              30 mapped sources
paper_evaluation:        blocked
  provenance gate:       passed (30 mapped sources)
  scope_alignment:       partial (0.01 overlap, 1 intent term)
  conclusion_support:    blocked — 2 empirical claims lack [RESULT-N] backing
```

## Blocked claims analysis

The conclusion checker correctly identified 2 unbacked empirical claims:

1. "We demonstrate that this unified architecture significantly outperforms
   conventional pipelines" — no [RESULT-N] citation
2. "We demonstrate the end-to-end training of this architecture" — no [RESULT-N]

These are broad architectural claims that should cite [RESULT-N] markers.
The markers exist in the paper but not in these specific claim sentences.
This is LLM paper-synthesis variance, not a code blocker — the experiment
executed correctly, the markers are present, and the checker is doing its job.

## Direction handling verification

```text
All 6 result_markers carry direction=higher_better from the spec.
The direction metadata flowed through: spec → manifest → marker construction → persistence.
This confirms the D3 structural direction fix works in a live run.
```
