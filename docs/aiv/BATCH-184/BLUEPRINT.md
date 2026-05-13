# BATCH-184 BLUEPRINT

## Batch Goal
Surgically fix the orchestrator so pipeline.yaml is the actual config source.
Delete the pass-through DAG wrapper. Keep what works.

## The Problem
The DAG rebuild (B180-B183) created 7 new files that wrap the existing orchestrator
without solving the root problems: scattered config, no structured logging, unpredictable behavior.

## The Solution
4 surgical edits to orchestrator.py + delete the wrapper:

### TASK-01: YAML-Driven Strategy Selection
Replace strategy preset registry with pipeline.yaml lookup.
Delete StrategyRegistry dependency from __init__.

### TASK-02: Structured Stage Logging
Add StageLogger.log() call inside _record_stage().
One JSON line per stage — config snapshot, inputs, outputs, elapsed time.

### TASK-03: dry_run() Method
Add dry_run(domain, strategy) that reads YAML and prints the execution plan
with model assignments, without executing.

### TASK-04: Clean Up
- Add TrimmerStage to _build_stages() (after ingestion)
- Delete backend/pipeline/dag/adapter.py, runner.py, context.py, registry.py
- Keep: pipeline.yaml, stage_log.py, trimmer.py, dataset_generator.py, eval_sidecar.py
- Update API endpoint POST /run/dag to use orchestrator directly

## Test Plan
- Existing 2,750+ tests must not break
- 3 new tests: YAML strategy resolution, stage logging, dry_run output
- Live E2E: trigger run via /run/dag, verify stage log written

## Acceptance Criteria
- [ ] pipeline.yaml is the ONLY strategy config source
- [ ] Every stage writes a JSON log entry
- [ ] dry_run() prints all stages with model assignments
- [ ] TrimmerStage runs after ingestion
- [ ] DAG wrapper files deleted
