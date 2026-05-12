BATCH BLUEPRINT — AIV v5.3
Batch ID: BATCH-RAG-03
Lead: Craft Agent | Date: 2026-05-13
Status: LEAD OVERRIDE §5.3

OBJECTIVE: Build LLM-as-judge faithfulness scorer that evaluates whether
generated proposals are grounded in source papers.

TASKS:
  TASK-01: FaithfulnessReport data model
  TASK-02: FaithfulnessScorer — LLM rates claims against source text
  TASK-03: Wire into post-proposal-synthesis stage
  TASK-04: Tests (~8)

FILES TO CREATE:
  backend/pipeline/evaluation/faithfulness_scorer.py
  backend/tests/test_pipeline/test_rag03_faithfulness.py

FILES TO MODIFY:
  backend/pipeline/orchestrator.py (faithfulness hook after proposal_synthesis)

HARD BOUNDARIES:
  HB-1: Only adds to orchestrator.py faithfulness hook
  HB-2: Uses local LLM only (LM Studio) — no cloud cost
  HB-3: Graceful degradation if LM Studio offline
  HB-4: Scores stored in proposal metadata, never block pipeline
