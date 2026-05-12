BATCH BLUEPRINT — AIV v5.3
Batch ID: BATCH-RAG-01
Lead: Craft Agent | Date: 2026-05-12
Status: LEAD OVERRIDE §5.3

OBJECTIVE: Build synthetic benchmark generator and retrieval benchmark runner.

TASKS:
  TASK-01: Benchmark data models (BenchmarkQuestion, BenchmarkDataset)
  TASK-02: BenchmarkGenerator — LLM generates questions from paper abstracts
  TASK-03: RetrievalBenchmarkRunner — runs search, measures if correct papers found
  TASK-04: API endpoints for benchmark generation and retrieval
  TASK-05: Tests (~10)

FILES TO CREATE:
  backend/pipeline/evaluation/benchmark_models.py
  backend/pipeline/evaluation/benchmark_generator.py
  backend/pipeline/evaluation/retrieval_benchmark.py
  backend/api/routes/evaluation.py
  backend/tests/test_pipeline/test_rag01_benchmark.py

FILES TO MODIFY:
  backend/api/app.py (register evaluation router)

HARD BOUNDARIES:
  HB-1: No existing modules modified except app.py router registration
  HB-2: All new code in backend/pipeline/evaluation/
  HB-3: No frontend changes
  HB-4: Uses local LM Studio only (no cloud cost for benchmark generation)
