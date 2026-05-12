BATCH BLUEPRINT — AIV v5.3
Batch ID: BATCH-RAG-04
Lead: Craft Agent | Date: 2026-05-13
Status: LEAD OVERRIDE §5.3

OBJECTIVE: Persist all evaluation metrics to DB, integration test,
and run full evaluation on existing data.

TASKS:
  TASK-01: pipeline_metrics DB table + migration
  TASK-02: Metrics persistence service
  TASK-03: Integration test: benchmark → metrics → verify stored
  TASK-04: Update STATE.md
  TASK-05: Tests (~6)

FILES TO CREATE:
  alembic/versions/008_pipeline_metrics.py
  backend/pipeline/evaluation/metrics_persistence.py
  backend/tests/test_pipeline/test_rag04_integration.py

FILES TO MODIFY:
  backend/db/models.py (PipelineMetric model)
  docs/aiv/STATE.md

HARD BOUNDARIES:
  HB-1: New DB table only (no schema changes to existing tables)
  HB-2: Integration test uses mock search
  HB-3: All metrics queryable via existing API
