BATCH BLUEPRINT — AIV v5.3
Batch ID: BATCH-RAG-02
Lead: Craft Agent | Date: 2026-05-12
Status: LEAD OVERRIDE §5.3

OBJECTIVE: Build standalone retrieval metrics module with MRR, nDCG@K, Hit Rate.
Wire into orchestrator as post-literature-search hook.

TASKS:
  TASK-01: retrieval_metrics.py — pure metric computation functions
  TASK-02: Orchestrator hook — compute metrics after literature_search stage
  TASK-03: Store metrics in pipeline run metadata
  TASK-04: API endpoint GET /api/v1/pipeline/runs/{id}/metrics
  TASK-05: Tests (~8)

FILES TO CREATE:
  backend/pipeline/evaluation/retrieval_metrics.py
  backend/tests/test_pipeline/test_rag02_retrieval_metrics.py

FILES TO MODIFY:
  backend/pipeline/orchestrator.py (metrics hook after literature_search)

HARD BOUNDARIES:
  HB-1: Only modifies orchestrator.py (metrics hook injection)
  HB-2: Pure math functions, no external deps
  HB-3: Metrics logged, never block pipeline
  HB-4: Graceful failure — metrics computation errors don't fail the pipeline
