BATCH BLUEPRINT — AIV v5.3
Batch ID: BATCH-RAG-05
Lead: Craft Agent | Date: 2026-05-13
Status: LEAD OVERRIDE §5.3

OBJECTIVE: Build token budget guard that trims document chunks before
LLM calls to prevent context window overflow.

TASKS:
  TASK-01: TokenCounter using tiktoken
  TASK-02: TokenBudgetGuard — drops low-score chunks if over budget
  TASK-03: Config: token_budget_per_stage setting
  TASK-04: Tests (~8)

FILES TO CREATE:
  backend/pipeline/knowledge/token_budget.py
  backend/tests/test_pipeline/test_rag05_token_budget.py

HARD BOUNDARIES:
  HB-1: New module only — no existing file modifications
  HB-2: tiktoken is only new runtime dep (already installed)
  HB-3: Guard never blocks pipeline, only trims input
