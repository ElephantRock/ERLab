BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-64
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead (Ivory Wolf Session)
Date Issued:              2026-05-04
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Parallel

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Add objective, computable quality metrics for research ideas
that do not depend on LLM judgment — reference uniqueness,
gap coverage, citation density, method specificity, prior art distance.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Implement MechanicalMetricsCalculator with 5 metric functions
  - Integrate metrics into idea scoring pipeline
  - Display metric breakdown on idea detail API response

What the code MUST NOT do:
  - Must not replace LLM-based scoring (supplement only)
  - Must not modify existing quality gate logic
  - Must not change the ideas DB schema

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Backend:  python -m ruff check backend/

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
HB-01: Mechanical metrics MUST return values in [0.0, 1.0] range.
HB-02: No LLM API calls allowed in mechanical metrics — pure computation.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
New file: backend/pipeline/evaluation/mechanical_metrics.py

MechanicalMetricsCalculator:
  - reference_uniqueness(idea, all_papers) -> float
    % of cited papers not previously cited in same domain runs
  - gap_coverage(idea, gaps) -> float
    % of identified gaps addressed by idea's proposed method
  - citation_density(idea, supporting_papers) -> float
    normalized avg citation count of supporting papers
  - method_specificity(idea) -> float
    count of concrete, testable claims / max_claims
  - prior_art_distance(idea, closest_papers) -> float
    1 - cosine_similarity(idea_embedding, closest_paper_embedding)

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
None — independent batch.

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline: 178 backend passing, 343 frontend passing
  Expected delta: +6 backend tests
  Expected total: 184 backend, 343 frontend

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-64/TASK-01 — MechanicalMetricsCalculator
  Files: backend/pipeline/evaluation/mechanical_metrics.py (create),
         backend/tests/test_pipeline/test_mechanical_metrics.py (create)
  Tests: 5 unit tests (one per metric) + 1 integration (composite score)
  AC-01-01: All metrics return [0.0, 1.0] (HB-01)
  AC-01-02: Zero LLM calls (HB-02)

TASK-02: BATCH-64/TASK-02 — Scoring Integration
  Files: backend/pipeline/stages.py (modify — call mechanical metrics after idea gen),
         backend/api/routes/ideas.py (modify — include metrics in response)
  Tests: 1 integration test
  AC-02-01: Mechanical metrics included in idea detail API response
  AC-02-02: Composite score weights: 40% LLM + 30% mechanical + 30% novelty/feasibility

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: All 5 metrics computable without LLM calls
  BAC-02: Metrics visible in API response
  BAC-03: CHANGELOG.md updated
  BAC-04: Documents archived under /docs/aiv/BATCH-64/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

Reviewer Report ID:       REVIEW-BATCH-64-2026-05-04
Review Cycle:             1
Lead Decision:            [x] ACCEPT
Zero flags.

Blueprint Version: 1.0
Lead Sign: Lead (Ivory Wolf) 2026-05-04 17:16

═══════════════════════════════════════════════════════════
