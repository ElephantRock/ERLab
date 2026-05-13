# BATCH-182 BLUEPRINT

## Batch Goal
Implement the two remaining offline tools from the orchestrator rebuild plan:
- Dataset Generator: reads historical runs from SQLite, produces benchmark JSON
- Eval Sidecar: reads stage logs + benchmark, computes metrics, writes SQLite

## Tasks

### TASK-01: Dataset Generator
**File:** `backend/pipeline/dag/dataset_generator.py` (new)

Reads completed pipeline runs from SQLite, produces a benchmark JSON file containing:
- run_id, domain, strategy, papers_count
- gap titles, idea titles, proposal word counts
- stage report data (elapsed times, skipped stages)
- Timestamps

### TASK-02: Eval Sidecar
**File:** `backend/pipeline/dag/eval_sidecar.py` (new)

Post-hoc evaluation tool:
- Reads stage logs from `logs/pipeline/{run_id}.jsonl`
- Reads benchmark from dataset generator output
- Computes metrics: total_elapsed, stage_count, skipped stages, papers_to_ideas_ratio,
  avg_gap_confidence, avg_proposal_word_count, citation_fabrication_rate, reranker_used
- Writes metrics to SQLite `evaluation_metrics` table

## Test Plan
- 5 tests for dataset generator (empty DB, populated DB, field presence, run filtering)
- 6 tests for eval sidecar (log loading, metric computation, skip detection, sidecar summary)
- No regression on BATCH-180/181 (33 tests)

## Acceptance Criteria
- [ ] Dataset generator produces valid JSON from 65 completed runs
- [ ] Eval sidecar computes all 8 metric categories
- [ ] Both tools work as CLI scripts: `python -m backend.pipeline.dag.dataset_generator`
