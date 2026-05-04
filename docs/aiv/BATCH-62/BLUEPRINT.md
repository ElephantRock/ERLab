BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-62
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
Implement a TreeSearchEngine with beam search over the idea space,
and an idea recombination operator that synthesizes novel ideas
from two parent ideas — proven by Google (arXiv 2509.06503) to
produce 44% recombinations that beat both parents.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Implement TreeSearchEngine class that performs beam search: expand N
    candidates → score → prune to K → repeat for D depth levels
  - Implement recombination operator: given 2 parent ideas, generate a child
    idea that combines the strongest elements of both
  - Both must be independently testable without running a full pipeline

What the code MUST NOT do:
  - Must not modify the existing IdeaGenerationStage or orchestrator pipeline
  - Must not modify any existing provider, stage, or agent code
  - Must not add new API endpoints or CLI commands

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Backend:  python -m ruff check backend/
  Frontend: npx tsc --noEmit

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
HB-01: TreeSearchEngine MUST NOT call any LLM provider directly — it delegates
       to an IdeatorAgent passed via constructor injection.
HB-02: Recombination MUST produce exactly 1 child idea per pair of parents,
       with a traceable lineage (parent_idea_ids field).
HB-03: Beam width MUST be capped at 10 regardless of configuration — no
       unbounded expansion that could exhaust LLM budgets.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
New file: backend/pipeline/generation/tree_search.py

TreeSearchEngine config:
  - beam_width: int (default 3, max 10 per HB-03)
  - max_depth: int (default 3)
  - ideas_per_node: int (default 5)
  - recombination_rate: float (default 0.3 — 30% of expansions use recombination)

TreeNode dataclass:
  - idea: IdeaCandidate | None (None for root)
  - children: list[TreeNode]
  - score: float
  - depth: int
  - parent_ids: list[str] (lineage tracking)

IdeaCandidate model (existing, from backend/pipeline/generation/models.py):
  - Has fields: title, problem_statement, proposed_method, expected_contributions,
    novelty_rationale, evaluation_approach, overall_score

New field on IdeaCandidate (optional, for lineage):
  - parent_idea_ids: list[str] | None

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
- TreeSearchEngine is a pure search algorithm — it does not manage state
- The IdeatorAgent (injected) is authoritative for idea generation
- Scoring uses the existing Borda tournament from generation/borda.py
- Recombination uses the injected provider's complete() method

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
BATCH-14: IdeaCandidate model exists (verified: yes)
BATCH-10: Borda tournament exists in generation/borda.py (verified: yes)
BATCH-12: IdeatorAgent exists in generation/ideator_agent.py (verified: yes)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  161 backend passing, 339 frontend passing
  Expected delta (all Tasks):      +8 backend tests
  Expected total at Batch close:   169 backend passing, 339 frontend passing

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-62/TASK-01 — Implement TreeSearchEngine with Beam Search
  Description:      Create the TreeSearchEngine class that performs iterative
                    beam search over the idea space. At each depth level,
                    expand the top-K candidates, score all children, prune
                    back to K, and repeat.
  Files in scope:
    - backend/pipeline/generation/tree_search.py (create)
    - backend/tests/test_pipeline/test_tree_search.py (create)
  Depends on:       None
  Required Tests:
    | Test ID          | Type | Pass Criteria                                              |
    |:-----------------|:-----|:-----------------------------------------------------------|
    | TEST-62-01-01    | unit | Beam search produces K candidates at each depth level      |
    | TEST-62-01-02    | unit | Pruning keeps only top-K by score                          |
    | TEST-62-01-03    | unit | Max depth is respected (no deeper expansion)               |
    | TEST-62-01-04    | unit | Beam width capped at 10 (HB-03)                            |
    | TEST-62-01-05    | unit | Final results are sorted by score descending               |
  Acceptance Criteria:
    AC-01-01: TreeSearchEngine.search() returns list[IdeaCandidate] sorted by score
    AC-01-02: Beam width is enforced at every depth level
    AC-01-03: Engine delegates to IdeatorAgent for generation (HB-01)

TASK-02: BATCH-62/TASK-02 — Idea Recombination Operator
  Description:      Implement recombination logic that takes 2 parent ideas
                    and produces 1 child idea combining the strongest elements
                    of both. Uses LLM provider to synthesize the combination.
  Files in scope:
    - backend/pipeline/generation/recombination.py (create)
    - backend/tests/test_pipeline/test_recombination.py (create)
  Depends on:       None
  Required Tests:
    | Test ID          | Type | Pass Criteria                                              |
    |:-----------------|:-----|:-----------------------------------------------------------|
    | TEST-62-02-01    | unit | Recombination produces exactly 1 child (HB-02)             |
    | TEST-62-02-02    | unit | Child has parent_idea_ids set with both parent IDs (HB-02) |
    | TEST-62-02-03    | unit | Recombination delegates to provider.complete(), not directly|
  Acceptance Criteria:
    AC-02-01: recombine(parent_a, parent_b) returns IdeaCandidate with lineage
    AC-02-02: parent_idea_ids contains both parent IDs
    AC-02-03: Provider is injected, not created internally

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: TreeSearchEngine can run a full beam search with mocked IdeatorAgent
  BAC-02: Recombination produces traceable child ideas with lineage
  BAC-03: CHANGELOG.md updated with BATCH-62 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-62/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

Reviewer Report ID:       REVIEW-BATCH-62-2026-05-04
Review Cycle:             1
Lead Decision:            [x] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

CHK-13 Flag (empty input): Not acted on. Assistant should return empty list
for zero-gap input. No dedicated test required.

Blueprint Version after response: 1.0 (no revision needed)
Lead Sign:                Lead (Ivory Wolf) 2026-05-04 16:19

═══════════════════════════════════════════════════════════
