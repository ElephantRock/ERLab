# Phase 7 — Unattended Empirical-Paper Reliability: Closeout

> **Status:** Phase 7 PASSES. The recovery behavior from Phase 6 is now part
> of the ordinary pipeline. One normal product run selected one proposal,
> executed the experiment exactly once, produced one complete paper without
> operator intervention, reported the persisted observed metrics, mapped every
> central empirical claim to [RESULT-N] durably, preserved all [SOURCE-N]
> provenance, survived restart (15/15 hashes identical), reproduced the
> experiment within frozen tolerances (diff=0.0), and left the canonical
> verification green.

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
Durable RESULT-marker linkage                   COMPLETE (7H-persist)
Durable non-selected proposal state             COMPLETE (7H-persist)
Full restart persistence proof                  PASS (15/15 hashes identical)
Phase 7 acceptance                              MET
```

## Acceptance criteria

```text
selects one proposal                                     YES (proposal 52, feasibility=7.6)
executes the experiment exactly once                     YES (experiment_result id=11)
produces one complete paper without operator intervention YES (1829 words, 7/7 sections)
survives a synthesis timeout via checkpoint recovery     N/A (monolithic succeeded; mechanism proven in 7F)
reports the persisted observed metrics                   YES (baseline=0.333, model=0.967, improvement=0.633)
maps every central empirical claim to [RESULT-N]         YES (6 occurrences, 3 markers, durable map persisted)
preserves all [SOURCE-N] provenance                      YES (7 markers, all mapped, 30-entry source_map)
survives restart                                         YES (15/15 hashes identical post-restart)
reproduces the experiment within frozen tolerances       YES (all metrics diff=0.000000, seed=42)
leaves canonical backend and frontend verification green YES (backend: 4919 pass / 0 fail; frontend: 988 pass / 0 fail)
```

## Durable persistence corrections (7H-persist)

The initial 7H closeout reported three persistence gaps. All three are now
resolved through code fixes + backfill + restart proof.

### Finding 1: RESULT mapping was not durable

**Problem:** The in-memory result_markers map (RESULT-1→baseline_accuracy,
RESULT-2→improvement, RESULT-3→model_accuracy) was not persisted to the DB.
The `experiment_result_id` was not set in the proposal's paper_meta_json.
After restart, [RESULT-N] could not resolve through persisted state.

**Fix (commit c04fc14):** `_extract_paper_artifact` now accepts `result_markers`
and persists a `result_markers` array in paper_meta_json with each marker's:
```json
{
  "marker": "RESULT-1",
  "metric_id": "baseline_accuracy",
  "observed_value": 0.333333,
  "experiment_result_id": 11,
  "artifact_path": "metrics.json",
  "artifact_sha256": "212a34a3fac2cd5d..."
}
```
Plus an `experiment_result_id` field linking the paper to the ExperimentResult.

**Backfilled run_2a9090090976** without paper regeneration or experiment rerun.

### Finding 2: Non-selected proposal state was not persisted

**Problem:** The non-selected proposal (id=51) had empty paper_meta_json
because `_extract_paper_artifact` returned (None, None) when there was no
`full_paper`.

**Fix (commit c04fc14):** When a proposal has `experiment_status =
not_selected_for_experiment` but no paper, `_extract_paper_artifact` now
returns a minimal metadata dict:
```json
{
  "status": "not_requested",
  "experiment_status": "not_selected_for_experiment",
  "paper_status": "not_requested"
}
```

### Finding 3: Checkpoint inspection ≠ restart proof

**Problem:** The initial restart check only verified the checkpoint file
existed. The acceptance test required an actual backend restart with
post-restart reload and hash comparison.

**Resolution:** Performed a real backend restart. Captured 15 pre-restart
hashes (experiment count, manifest, paper, RESULT-map, SOURCE-map, eval
payload, non-selected state, 8 export files). After restart, all 15
reloaded through the persistence path with **identical hashes**.

## Restart persistence proof (7H-persist-5)

```text
Pre-restart capture → backend restart → post-restart reload

  experiment_count           13 → 13            IDENTICAL
  exp11_manifest_sha256      ✓                  IDENTICAL
  paper_md_sha256            ✓                  IDENTICAL
  result_map_sha256          ✓                  IDENTICAL
  source_map_sha256          ✓                  IDENTICAL
  eval_payload_sha256        ✓                  IDENTICAL
  non_selected_meta_sha256   ✓                  IDENTICAL
  export_README.md           ✓                  IDENTICAL
  export_brief.json          ✓                  IDENTICAL
  export_gaps.json           ✓                  IDENTICAL
  export_ideas.json          ✓                  IDENTICAL
  export_log.jsonl           ✓                  IDENTICAL
  export_notes.md            ✓                  IDENTICAL
  export_plan.json           ✓                  IDENTICAL
  export_quality_report.json ✓                  IDENTICAL

  Total: 15/15 IDENTICAL
```

Post-restart RESULT marker resolution through persisted state:
```text
  RESULT-1 → baseline_accuracy=0.333333  exp_id=11  artifact=212a34a3fac2cd5d...
  RESULT-2 → improvement=0.633333        exp_id=11  artifact=212a34a3fac2cd5d...
  RESULT-3 → model_accuracy=0.966667     exp_id=11  artifact=212a34a3fac2cd5d...
```

Post-restart non-selected state:
```text
  proposal 51: experiment_status=not_selected_for_experiment
  proposal 51: paper_status=not_requested
```

## 7G run details

See `PHASE_7_7G_LIVE_RUN.md` for the full run manifest.

```text
run_id:            run_2a9090090976
duration:          ~3h 48m (fully unattended)
experiment:        phase5-pilot-v1 (Iris logistic regression)
paper:             1829 words, monolithic, 7/7 sections
eval:              ready (provenance + scope + conclusion gates passed)
```

## Defects found and fixed during Phase 7

### 1. ExperimentExecutionStage._get_metadata crash (commit 2bc04d1)

Found by the first 7G attempt. The non-selected-proposal marking loop
crashed before the experiment could execute.

### 2. Unified service bypassed injected synthesizer (commit 2bc04d1)

`synthesize_paper()` now accepts `synthesizer_override`.

### 3. batch153/batch174 fake-provider responses below 200-word threshold

Test data expanded to meet the unified service's quality gates.

### 4. RESULT-marker linkage not durable (commit c04fc14)

`_extract_paper_artifact` now persists result_markers + experiment_result_id.

### 5. Non-selected proposal state not persisted (commit c04fc14)

Minimal paper_meta_json now written for non-selected proposals.

## Verification

### Backend (7H-4)

```text
selector:           pytest -m "not slow and not integration"
result:             4919 passed, 22 skipped, 37 deselected, 0 failures
```

### Frontend (7H-5)

```text
vitest:             122 test files, 988 tests passed, 0 failures
tsc --noEmit:       PASS (exit code 0, no type errors)
```

### Focused suites (7H-persist-6)

```text
Phase 7 controlled proof:    18 passed
Phase 7H persistence:         8 passed
Phase 5 controlled proof:    55 passed
Phase 6 recovery proof:      16 passed
Architecture:                 3 passed
batch153 + batch174:         19 passed
```

### Experiment reproduction (7H-2)

```text
seed:              42
                   baseline_accuracy  diff=0.000000  PASS
                   model_accuracy     diff=0.000000  PASS
                   improvement        diff=0.000000  PASS
```
