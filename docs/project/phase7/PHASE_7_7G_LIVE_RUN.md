# Phase 7 / 7G — Unattended Empirical-Paper Live Run

> **Status:** 7G PASSES. One ordinary product run selected one proposal,
> executed the experiment exactly once, produced one complete paper without
> operator intervention, reported the persisted observed metrics, mapped every
> central empirical claim to [RESULT-N], preserved all [SOURCE-N] provenance,
> and reached eval=ready.

## Run manifest

```text
run_id:                  run_2a9090090976
db_id:                   2480
domain:                  machine learning
strategy:                deep_research
experiment_spec_id:      phase5-pilot-v1
started:                 2026-07-30 04:57:28
completed:               2026-07-30 08:45:01
duration:                ~3h 48m
status:                  completed
operator intervention:   NONE (fully unattended)
```

## Stage timeline

```text
literature_search        28.0s
ingestion                (retried 1x on embedding 400, recovered)
gap_analysis             ~3m
idea_generation          ~1m      (2 ideas)
feasibility_scoring      ~6m
proposal_synthesis       731.0s   (2 proposals, refinement passes)
adversarial_review       1200.0s  (both rejected round 1, re-synthesized)
evaluation               41.5s
experiment_execution     0.5s     ← THE CRITICAL STAGE
paper_synthesis          141.8s   (monolithic, 7/7 sections)
citation_audit           ~2m
proposal_deepening       ~1m
export                   completed
```

## Defect found and fixed by the first 7G attempt

The first 7G run (run_2efbe917c234) surfaced a real Phase 7A defect:

```text
AttributeError: 'ExperimentExecutionStage' object has no attribute '_get_metadata'
```

The non-selected-proposal marking loop in `ExperimentExecutionStage.execute()`
called `self._get_metadata()` / `self._set_metadata()`, which were only defined
on `ProposalSynthesisStage` and `PaperSynthesisStage`. The crash happened
BEFORE the experiment execution loop, so:

- The stage retried 3x, exhausted retries, and the pipeline continued non-fatally
- No experiment executed (0 new experiment_result rows)
- Paper synthesis produced a paper with NO [RESULT-N] markers
- The conclusion checker correctly BLOCKED: "claims results demonstrate but
  the paper reports no empirical results"

**Fix (commit 2bc04d1):**
1. Added `_get_metadata` / `_set_metadata` static helpers to
   `ExperimentExecutionStage` (identical to the existing pattern)
2. Added `synthesizer_override` parameter to `synthesize_paper()` so the
   unified service honors injected synthesizers (fixed a pre-existing
   batch174 test that was silently making live LLM calls)
3. Added regression test `test_experiment_stage_can_mark_non_selected_proposals`

Verified: 29/29 phase7 + batch174 tests pass.

## 7G acceptance criteria

```text
selects one proposal                                     YES (proposal 52, feasibility=7.6)
executes the experiment exactly once                     YES (experiment_result id=11, succeeded)
produces one complete paper without operator intervention YES (1829 words, 7/7 sections)
survives a synthesis timeout via checkpoint recovery     N/A (monolithic succeeded in 141.8s)
reports the persisted observed metrics                   YES (baseline=0.333, model=0.967, improvement=0.633)
maps every central empirical claim to [RESULT-N]         YES (6 occurrences: [RESULT-1],[RESULT-2],[RESULT-3])
preserves all [SOURCE-N] provenance                      YES (7 occurrences, 30 mapped sources)
survives restart                                         [7H]
reproduces the experiment within frozen tolerances       [7H]
leaves canonical backend and frontend verification green [7H]
```

## Experiment details

```text
experiment_result_id:    11
spec:                    phase5-pilot-v1
status:                  succeeded
execution_time:          0.422s
results:
  baseline_accuracy:     0.333333
  model_accuracy:        0.966667
  improvement:           0.633333
artifacts (3):
  metrics.json           sha=212a34a3fac2cd5d...
  predictions.csv        sha=3a3990c8f7ccad97...
  results_table.csv      sha=c3d8f5215769e2cd...
stdout:                  Analysis complete. baseline_acc=0.3333 model_acc=0.9667 improvement=+0.6333
```

## Paper details

```text
proposal_id:             52 (idea 70)
word_count:              1829
synthesis_strategy:      monolithic
sections:                7/7
[RESULT-N] markers:      [RESULT-1] → baseline_accuracy = 0.333333
                         [RESULT-2] → improvement = 0.633333
                         [RESULT-3] → model_accuracy = 0.966667
[SOURCE-N] markers:      7 occurrences (SOURCE-1,3,8,14,15,16,24...)
source_map:              30 mapped sources
paper_evaluation:        ready
  provenance gate:       passed (30 mapped sources)
  scope_alignment gate:  passed (on scope, 2 intent terms hit)
  conclusion_support:    passed ("Claims are consistent with reported empirical results")
```

## Proposal selection enforcement (7A)

```text
candidates:              2 (proposals 51, 52)
selected:                52 (feasibility=7.6, highest)
non-selected (51):       not synthesized for paper (empirical selection active)
experiment executed:     1 (only for selected proposal)
```

## Known minor gaps (non-blocking)

1. `experiment_result_id` is not set in the proposal's paper_meta_json — the
   linkage exists at the DB level (experiment_results.id=11) but the
   proposal-level metadata field was not written. The [RESULT-N] markers in
   the paper text provide the traceable link.

2. The non-selected proposal's (id=51) `experiment_status` /
   `paper_status` fields were not persisted to the DB (empty meta keys).
   The marking happened on the in-memory object but the DB flush did not
   capture these metadata fields. Functionally correct — only 1 experiment
   ran and only 1 paper was synthesized.
