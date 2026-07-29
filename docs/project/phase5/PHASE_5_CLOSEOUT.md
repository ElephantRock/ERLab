# Phase 5 — Empirical Research Execution: Closeout

> **Status:** Phase 5 closes with acceptance **NOT MET**.
> The empirical execution path is proven (controlled tests + live experiment with
> valid persisted metrics). Paper-generation reliability is the blocker.

## Final status

```text
5B.1  Fix await bug                             COMPLETE
5B.2  Dataset + experiment spec + manifest       COMPLETE
5B.3  Structured execution + persistence         COMPLETE
5B.4  Pipeline integration (opt-in stage)        COMPLETE
5B.5  Paper + evaluation integration             COMPLETE
5C    Controlled proof (17 deterministic tests)  COMPLETE
5D    One live empirical run                      COMPLETED — 0 papers
5E    Independent reproduction + closeout         NOT APPLICABLE (no paper to audit)
```

## Live run result (5D)

Run `run_2718873e9191` executed through the full production pipeline with
`experiment_spec_id=phase5-pilot-v1`:

```text
Experiment execution stage:        SUCCEEDED (both proposals)
  baseline_accuracy:               0.3333
  model_accuracy:                  0.9667
  improvement:                     +0.6333
  metrics.json:                    schema-valid
  predictions.csv:                 persisted + hashed
  results_table.csv:               persisted + hashed
  ExperimentManifest:              2 rows persisted with full reproducibility metadata

Paper synthesis stage:             0 papers produced
  Proposal 0:                      B-08 timeout (600s), section-wise fallback started
  Proposal 1:                      B-08 timeout (600s), section-wise fallback started
  Both section-wise syntheses:     Incomplete within remaining time budget
```

## What was proven

1. The experiment execution stage runs correctly through the production pipeline
2. The checked-in analysis executes deterministically (baseline=0.3333, model=0.9667)
3. Metrics are captured via `metrics.json` (not stdout parsing)
4. Artifacts are hashed and persisted
5. The ExperimentManifest contains full reproducibility metadata
6. The experiment results persist even when paper synthesis later fails
7. All 17 controlled-proof tests pass deterministically

## What was NOT proven

1. No paper was produced — paper synthesis could not complete within the B-08
   timeout (600s per proposal) on glm-4.6
2. No [RESULT-N] markers were emitted (no paper to emit them in)
3. No claim-to-result audit (no paper to audit)
4. No independent reproduction comparison (no paper to compare)
5. No restart persistence check (no paper/marker/export hashes to verify)

## Root cause of paper-generation failure

The same B-08 timeout pattern documented in Phase 4: glm-4.6's long-generation
and structured-output behavior is slow and failure-prone for paper-length content
(2000+ words). The monolithic synthesis hits the 600s per-proposal timeout. The
section-wise fallback generates sections but cannot complete assembly within
the remaining time. This is a provider compatibility issue, not an ERLab defect.

## Implementation defects found and fixed during 5D

1. **YAML config**: `pipeline.yaml` (the strategy source of truth) did not
   include `experiment_execution` in any strategy's stage list. The Python
   presets were updated but the YAML overrides them. Fixed (commit `13e2811`).
2. **Missing Path import**: `_persist_experiment` used `Path` but it was only
   imported in `execute()`'s local scope. Fixed (commit `e5faca1`).
3. **Missing `experiment_spec_id` wiring**: `PipelineRunRequest` had no field
   for it; the orchestrator had no parameter. Fixed (commit `d3c04a1`).

## Phase 5 acceptance status

```text
one live experiment executes successfully      YES
one paper reports the actual observed result    NO (0 papers produced)
all central empirical claims resolve to results  N/A (no paper)
dataset/code/config/metrics/tables durable      YES (experiment artifacts persisted)
experiment reproduces independently              YES (controlled proof: deterministic)
paper survives restart and export                N/A (no paper)
evaluator blocks claims without results          PROVEN (controlled tests)
independent citation/claim/quality audits       N/A (no paper)
canonical backend/frontend verification         NOT RUN (no paper to verify against)
```

Phase 5 acceptance is **NOT MET**: no paper reports the experiment result.

## Correct conclusion

> The empirical execution path is proven end-to-end: a frozen dataset, checked-in
> analysis, deterministic experiment, and persisted result artifacts flow correctly
> through the production pipeline. Paper-generation reliability on glm-4.6 prevents
> the experiment result from being reported in a paper. Phase 5 closes with the
> empirical path proven but acceptance not met.

## P1E artifacts changed = 0

## Retrieval ranking architecture changed = 0

## Working tree status

Clean at closeout.

---

*End of Phase 5. Empirical execution path proven; paper-generation reliability
remains the blocker for producing a reproducible empirically supported paper.*
