# BATCH-181 BLUEPRINT

## Batch Goal
Bridge the new DAG runner to existing stage implementations. Add a trimmer stage. Wire DAGRunner into the pipeline API route so the front-end can trigger runs via the new orchestrator.

## Tasks

### TASK-01: Trimmer Stage
**File:** `backend/pipeline/dag/trimmer.py` (new)

A new `TrimmerStage(PipelineStage)` that:
1. Reranks `ctx.all_papers` by relevance (using existing reranker)
2. Truncates abstracts to `max_abstract_chars` (from YAML budgets)
3. Keeps top `trim_top_k` papers
4. Logs trim stats (before/after counts, avg abstract length)

The trimmer runs after `ingestion` and before `gap_analysis` in all strategies. It prevents GPU OOM on long abstracts and reduces noise from low-relevance papers.

### TASK-02: DAG-to-Stage Adapter
**File:** `backend/pipeline/dag/adapter.py` (new)

An adapter class that:
1. Instantiates the old `PipelineStage` subclasses from `stages.py`
2. Maps new `dag.StageContext` → old `stages.StageContext` before each stage
3. Maps old `stages.StageContext` → new `dag.StageContext` after each stage
4. Builds stages using the same construction as `PipelineOrchestrator._build_stages()`
5. Resolves the correct LLM provider per stage based on the model category from `STAGE_REGISTRY`

### TASK-03: Wire DAGRunner into API
**File:** `backend/api/routes/pipeline.py` (modify)

Add a new endpoint `POST /api/v1/pipeline/run/dag` that:
1. Accepts `{domain, strategy}` 
2. Creates a `DAGRunner` from `pipeline.yaml`
3. Runs `runner.execute(strategy, domain)` using the adapter
4. Returns the same response format as the existing run endpoint
5. Does NOT remove the old endpoint — both run side-by-side

## Test Plan
- 18 tests from BATCH-180 (no regression)
- 6 new tests for trimmer (rerank, truncate, top_k, stats)
- 6 new tests for adapter (context mapping, provider resolution)
- 3 new tests for API endpoint (trigger, status, error)

## Acceptance Criteria
- [ ] Trimmer stage limits papers to top_k, truncates abstracts
- [ ] Adapter correctly maps between old and new StageContext
- [ ] API endpoint triggers a full DAG-based pipeline run
- [ ] Existing 2765+ tests still pass (no regression)
