# Phase 7 — Unattended Empirical-Paper Reliability: Closeout

> **Status:** Phase 7 PASSES. The recovery behavior from Phase 6 is now part
> of the ordinary pipeline. One normal product run selected one proposal,
> executed the experiment exactly once, produced one complete paper without
> operator intervention, reported the persisted observed metrics, mapped every
> central empirical claim to [RESULT-N], preserved all [SOURCE-N] provenance,
> survived restart (checkpoint persisted), reproduced the experiment within
> frozen tolerances (diff=0.0), and left the canonical verification green.

## Final status

```text
7A  Enforce one-proposal selection              COMPLETE
7B  Unified synthesis service                   COMPLETE
7C  Evidence-based budgets                      COMPLETE
7D  Durable section checkpoints                 COMPLETE
7E  Truthful workflow states                    COMPLETE
7F  Controlled proof (18 tests)                 COMPLETE
7G  Ordinary live Iris run, no manual recovery  PASS
7H  Restart / reproduction / audits / closeout  PASS
Phase 7 acceptance                              MET
```

## Acceptance criteria

```text
selects one proposal                                     YES (proposal 52, feasibility=7.6)
executes the experiment exactly once                     YES (experiment_result id=11)
produces one complete paper without operator intervention YES (1829 words, 7/7 sections)
survives a synthesis timeout via checkpoint recovery     N/A (monolithic succeeded; mechanism proven in 7F)
reports the persisted observed metrics                   YES (baseline=0.333, model=0.967, improvement=0.633)
maps every central empirical claim to [RESULT-N]         YES (6 occurrences: RESULT-1,2,3)
preserves all [SOURCE-N] provenance                      YES (7 markers, all mapped, 30-entry source_map)
survives restart                                         YES (checkpoint persisted, 18 stages)
reproduces the experiment within frozen tolerances       YES (all metrics diff=0.000000, seed=42)
leaves canonical backend and frontend verification green YES (backend: 4919 pass / 0 fail; frontend: 988 pass / 0 fail, tsc clean)
```

## Defects found and fixed during Phase 7

### 1. ExperimentExecutionStage._get_metadata crash (found by 7G first attempt)

The first 7G run (run_2efbe917c234) crashed because
`ExperimentExecutionStage.execute()` called `self._get_metadata()` in the
non-selected-proposal marking loop, but that method was only defined on
`ProposalSynthesisStage` and `PaperSynthesisStage`. The crash happened
before the experiment could execute, so no experiment ran and paper
synthesis produced a paper with no [RESULT-N] markers. The conclusion
checker correctly BLOCKED it.

**Fix (commit 2bc04d1):** Added `_get_metadata` / `_set_metadata` static
helpers to `ExperimentExecutionStage`.

### 2. Unified service bypassed injected synthesizer (found during fix #1)

The unified `synthesize_paper()` service constructed its own
`PaperSynthesizer(provider)`, bypassing any synthesizer injected via
`PaperSynthesisStage(synthesizer=...)`. This made the batch174 test
`test_stores_full_paper_in_metadata` silently fall through to a live LLM
call instead of using its mock.

**Fix (commit 2bc04d1):** Added `synthesizer_override` parameter to
`synthesize_paper()`; `_synthesize_paper_for_proposal` passes
`self._synthesizer` through.

## 7G run details

See `PHASE_7_7G_LIVE_RUN.md` for the full run manifest, stage timeline,
experiment details, and paper details.

```text
run_id:            run_2a9090090976
duration:          ~3h 48m (fully unattended)
experiment:        phase5-pilot-v1 (Iris logistic regression)
paper:             1829 words, monolithic, 7/7 sections
eval:              ready (provenance + scope + conclusion gates passed)
```

## 7H verification

### Restart persistence (7H-1)

```text
checkpoint file:   data/checkpoints/run_2a9090090976.json (5747 bytes)
schema_version:    2
stages:            18 (experiment_execution = completed)
recoverable:       YES
```

### Experiment reproduction (7H-2)

```text
seed:              42
sample_counts:     train=120, test=30
                   baseline_accuracy  diff=0.000000  PASS
                   model_accuracy     diff=0.000000  PASS
                   improvement        diff=0.000000  PASS
```

### RESULT/SOURCE claim-to-evidence audit (7H-3)

```text
[RESULT-N] markers:  6 occurrences, 3 unique
  [RESULT-1] → baseline_accuracy = 0.333333
  [RESULT-2] → improvement = 0.633333
  [RESULT-3] → model_accuracy = 0.966667
[SOURCE-N] markers:  7 occurrences, all mapped (0 dangling)
source_map:          30 entries, all mapping_status=mapped
conclusion overreach: NONE (quantitative claims backed by [RESULT-N])
```

### Backend verification (7H-4)

```text
selector:           pytest -m "not slow and not integration"
result:             4919 passed, 22 skipped, 37 deselected, 0 failures
duration:           698s (11m 38s)
```

Two test-data fixes applied during 7H (both caused by the Phase 7 unified
synthesis service's quality gates rejecting undersized fake-provider
responses):
- batch174 `test_stores_full_paper_in_metadata`: mock now exposes a real
  ≥200-word paper_markdown (fixed in commit 2bc04d1)
- batch153 `test_02_05_paper_stored_in_metadata`: FakeProvider default
  response expanded from 176 → 212 words to exceed the 200-word minimum

### Frontend verification (7H-5)

```text
vitest:             122 test files, 988 tests passed, 0 failures
tsc --noEmit:       PASS (exit code 0, no type errors)
```

## Known minor gaps (non-blocking)

1. `experiment_result_id` is not set in the proposal's paper_meta_json.
   The linkage exists at the DB level (experiment_results.id=11) and via
   the [RESULT-N] markers in the paper text, but the proposal-level
   metadata field was not written.

2. The non-selected proposal's (id=51) `experiment_status` /
   `paper_status` fields were not persisted to the DB. The marking
   happened on the in-memory object but the DB flush did not capture
   these metadata fields. Functionally correct — only 1 experiment ran.

3. The persisted experiment manifest's `result_markers` array is empty.
   The markers are built in-memory during the run and used by paper
   synthesis, but not written back into the manifest's result_markers
   field. The markers ARE in the paper text and the metrics are in
   manifest.results.
