# Phase 5 — Empirical Research Execution: Closeout

> **Status:** Phase 5 closes with acceptance **NOT MET**.
> ERLab successfully executed and durably recorded a frozen empirical analysis
> through the live pipeline, but did not produce the required empirical paper.
> Phase 5 acceptance was not met because paper synthesis timed out before
> observed results could be linked to paper claims and exports.

## Final status

```text
5B.1  Fix await bug                             COMPLETE
5B.2  Dataset + experiment spec + manifest       COMPLETE
5B.3  Structured execution + persistence         COMPLETE
5B.4  Pipeline integration (opt-in stage)        COMPLETE
5B.5  Paper + evaluation integration             COMPLETE
5C    Controlled proof (17 deterministic tests)  COMPLETE
5D    Live experiment execution                  PASS (2 experiments succeeded)
5D    Paper production                           FAIL (0 papers)
5E    Independent reproduction                   COMPLETE (metrics match, hashes stable)
Final post-fix verification                      COMPLETE (pre-existing failures documented)
Phase 5 acceptance                               NOT MET
```

## Frozen contract deviation

The authorized pilot specified `proposal count: 1, experiment count: 1`. The
live run produced 2 ideas (tree-search idea generation found 2 viable branches
despite `ideas_per_round: 1`), leading to 2 proposals and 2 experiment
executions. The `ExperimentExecutionStage` runs for all proposals in the result
set — it does not constrain which proposals receive experiments. This is a
contract deviation: the pipeline did not enforce the frozen one-proposal
boundary.

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

### Paper synthesis failure analysis

Paper synthesis failed at the existing 600-second B-08 boundary. The result is
consistent with an interaction among glm-4.6 generation latency, synthesis
prompt size, fallback behavior, and ERLab's timeout policy. The evidence does
not isolate the provider as the sole cause. The timeout and fallback policy are
part of ERLab's product reliability boundary, even when provider latency
contributes.

## Attempt ledger

```text
Attempt 1: run_c50607bab6f7 (first live run)
  Terminal failure: experiment_execution stage skipped by strategy
  Root cause: pipeline.yaml (the strategy source of truth) did not include
    'experiment_execution' in any strategy's stage list. Python presets were
    updated but the YAML overrides them.
  Provider calls: full pipeline run (literature → paper synthesis)
  Code defect: missing stage in pipeline.yaml
  Repair: commit 13e2811 (fix(config): add experiment_execution to pipeline.yaml)
  Retry authorized: yes (transient config defect)

Attempt 2: run_2ad83ed1b6dd (retry after config fix)
  Terminal failure: experiment_execution stage ran but experiments failed:
    'name Path is not defined'
  Root cause: _persist_experiment used Path but it was only imported in
    execute()'s local scope
  Provider calls: full pipeline run (literature → paper synthesis)
  Code defect: missing Path import in _persist_experiment
  Repair: commit e5faca1 (fix(stage): add Path import)
  Retry authorized: yes (implementation defect found during retry)

Attempt 3: run_2718873e9191 (final retry after Path fix)
  Terminal state: completed with 0 papers
  Experiments: SUCCEEDED (both proposals, metrics persisted)
  Paper synthesis: 0 papers (B-08 timeout on both)
  Additional defect found: missing experiment_spec_id wiring from API to
    orchestrator (commit d3c04a1, fixed between attempts 1 and 2)
  No further retry authorized
```

## Independent reproduction (5E)

### Persistence check (post-restart)

```text
Backend restarted from HEAD 23bbafa
Both ExperimentResult rows reloaded successfully
Manifest data intact: dataset hash, code hash, metrics, artifact hashes
```

### Independent reproduction

```text
Dataset SHA-256 confirmed before execution: 1091a0df... (matches manifest)
Code SHA-256 confirmed before execution: af0cd605... (matches manifest)
Re-executed from clean temporary directory
Exit code: 0

Metric comparison (persisted vs reproduced):
  baseline_accuracy: 0.333333 vs 0.333333  diff=0.0      tolerance=0.001  PASS
  model_accuracy:    0.966667 vs 0.966667  diff=0.0      tolerance=0.001  PASS
  improvement:       0.633333 vs 0.633333  diff=0.0      tolerance=0.002  PASS

Artifact hash comparison (reproduced vs persisted):
  metrics.json:      MATCH
  predictions.csv:   MATCH
  results_table.csv: MATCH
```

Full reproducibility proven: all metrics within frozen tolerances (diff=0.0),
all artifact hashes identical.

## Final post-fix verification

```text
Phase 5 focused tests:           18 passed
Controlled Phase 5 proof:        17 passed
Architecture:                    41 passed
Ranking:                         253 passed, 3 skipped
Controlled integrations (P1+P2+P4): 14 passed
Migration tests:                 5 passed
Frontend typecheck:              PASS
Frontend tests:                  988 passed
Frontend build:                  PASS
Frontend lint:                   PASS
Frontend budgets:                all hold

Full canonical selector:         4857 passed, 3 failed, 47 skipped
  Real pytest exit code:          1 (FAILING)
  Status:                         FAILING
  No new backend failures were introduced by the Phase 5 closeout corrections.
  Three Batch 55 failures already present at ad8934d remain unresolved.
```

## What was proven

1. The experiment execution stage runs correctly through the production pipeline
2. The checked-in analysis executes deterministically (baseline=0.3333, model=0.9667)
3. Metrics are captured via `metrics.json` (not stdout parsing)
4. Artifacts are hashed and persisted
5. The ExperimentManifest contains full reproducibility metadata
6. The experiment results persist even when paper synthesis later fails
7. All 17 controlled-proof tests pass deterministically
8. Independent reproduction produces identical metrics and artifact hashes

## What was NOT proven

1. No paper was produced — paper synthesis timed out at the B-08 boundary
2. No [RESULT-N] markers were emitted (no paper to emit them in)
3. No claim-to-result audit (no paper to audit)
4. No restart persistence check on paper/marker/export hashes (no paper)

## P1E artifacts changed = 0

## Retrieval ranking architecture changed = 0

## Working tree status

Clean at closeout.

---

*End of Phase 5. ERLab successfully executed and durably recorded a frozen
empirical analysis through the live pipeline, but did not produce the required
empirical paper. Phase 5 acceptance was not met because paper synthesis timed
out before observed results could be linked to paper claims and exports.*
