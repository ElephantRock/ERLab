BATCH BLUEPRINT — BATCH-81
═══════════════════════════════════════════════════════════
Batch ID: BATCH-81 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-06 | Sequencing: SEQUENTIAL
───────────────────────────────────────────────────────────
GOAL: Score proposals on 5 dimensions (Novelty, Feasibility, Completeness,
Rigor, Clarity) with 0-1 scores and written justifications. Store as JSON
alongside proposals. Frontend displays as evaluation card.
───────────────────────────────────────────────────────────
SCOPE:
  MUST: ProposalEvaluator returns 5 dimension scores + justification each
  MUST: Evaluation stored in proposal metadata
  MUST: Frontend renders evaluation scores in idea-detail page
  MUST NOT: Modify proposal content
  MUST NOT: Block pipeline if evaluation fails
───────────────────────────────────────────────────────────
HARD BOUNDARIES:
  HB-01: Evaluation MUST NOT modify proposal text
  HB-02: Each dimension score MUST be in [0.0, 1.0]
  HB-03: Evaluation failure MUST NOT crash pipeline (fail-open)
───────────────────────────────────────────────────────────
LINT: python -m ruff check backend/ && python -m pytest --co -q
───────────────────────────────────────────────────────────
STATE.md: Updated BATCH-80 | 0 batches since | N/A audit
───────────────────────────────────────────────────────────
TEST BASELINE: 1,984 | Delta: +14 | Expected: 1,998
───────────────────────────────────────────────────────────
TASK-01: ProposalEvaluator Implementation (Critical)
  Files: backend/pipeline/evaluation/proposal_evaluator.py (NEW),
         backend/pipeline/evaluation/prompts/evaluation.md (NEW)
  Tests: 9 tests

TASK-02: Storage + Frontend Rendering (High)
  Files: backend/pipeline/persistence.py (MODIFY),
         frontend/src/components/ideas/evaluation-card.tsx (NEW),
         frontend/src/pages/idea-detail.tsx (MODIFY)
  Tests: 5 tests (storage round-trip, frontend component)
───────────────────────────────────────────────────────────
BAC-01: 5-dimension evaluation works for proposals
BAC-02: Evaluation stored with proposal
BAC-03: Frontend displays evaluation scores
BAC-04: CHANGELOG.md updated
BAC-05: All docs under /docs/aiv/BATCH-81/
═══════════════════════════════════════════════════════════
