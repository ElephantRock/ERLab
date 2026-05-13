"""DAG pipeline modules — config, logging, offline tools.

BATCH-184: The DAG runner and adapter were deleted. The orchestrator now
reads pipeline.yaml directly. This package contains:

- config.py: ConfigLoader for pipeline.yaml
- stage_log.py: StageLogger for structured JSON logging
- trimmer.py: TrimmerStage (reranks + truncates papers)
- dataset_generator.py: Offline benchmark from historical runs
- eval_sidecar.py: Post-hoc evaluation of pipeline runs
- pipeline.yaml: Single source of truth for models, budgets, strategies
"""
