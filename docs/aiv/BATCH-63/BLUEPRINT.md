BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-63
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead (Ivory Wolf Session)
Date Issued:              2026-05-04
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential (TASK-02 depends on TASK-01)

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Integrate TreeSearchEngine into the pipeline as a new TreeSearchStage
(replacing IdeaGenerationStage when tree_of_thought_enabled=True), and
create a frontend tree visualization component for the Run Detail page.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Create TreeSearchStage that uses TreeSearchEngine when config flag is enabled
  - Fall back to existing IdeaGenerationStage when flag is disabled
  - Store tree structure in PipelineResult for frontend consumption
  - Create React component that renders the search tree as an interactive SVG

What the code MUST NOT do:
  - Must not modify the existing IdeaGenerationStage code (only add alongside)
  - Must not change the pipeline_runs DB schema
  - Must not remove or alter any existing API endpoints

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Backend:  python -m ruff check backend/
  Frontend: npx tsc --noEmit

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
HB-01: TreeSearchStage MUST NOT activate unless tree_of_thought_enabled=True
       in settings — the default pipeline flow MUST remain unchanged.
HB-02: The frontend tree visualization MUST NOT make additional API calls —
       it renders from data embedded in the run detail response.
HB-03: The tree_search_result JSON blob stored in PipelineResult MUST NOT
       exceed 500KB per run (prevent DB bloat).

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
TreeSearchEngine (from BATCH-62): backend/pipeline/generation/tree_search.py
  - search() -> list[IdeaCandidate]
  - TreeNode dataclass with idea, children, score, depth, parent_ids

PipelineResult (existing): backend/pipeline/result.py
  - Add optional field: tree_data: dict | None = None
  - Contains serialized tree structure for frontend

Stage registration (existing): backend/pipeline/orchestrator.py
  - STAGE_ORDER list defines pipeline stages
  - IdeaGenerationStage at index 2 (after gap_analysis)

Frontend run detail (existing): frontend/src/pages/run-detail.tsx
  - Displays run results, ideas, gaps, proposals

Config: backend/config.py
  - tree_of_thought_enabled: bool = False (already exists)
  - tree_of_thought_max_depth: int = 3 (already exists)
  - tree_of_thought_beam_width: int = 2 (already exists)

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
- The orchestrator decides which stage to use based on config flag
- TreeSearchStage delegates to TreeSearchEngine (from BATCH-62)
- Frontend receives tree data as part of the existing run detail API response

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
BATCH-62: TreeSearchEngine + IdeaRecombinator must exist (verified: yes)
BATCH-25: Knowledge graph SVG rendering pattern (verified: exists)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  174 backend passing, 339 frontend passing
  Expected delta (all Tasks):      +5 backend, +3 frontend tests
  Expected total at Batch close:   179 backend, 342 frontend passing

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-63/TASK-01 — TreeSearchStage Pipeline Integration
  Description:      Create TreeSearchStage that wraps TreeSearchEngine,
                    integrates into the pipeline stage chain, and stores
                    tree data in PipelineResult for frontend consumption.
  Files in scope:
    - backend/pipeline/stages.py (modify — add TreeSearchStage class)
    - backend/pipeline/orchestrator.py (modify — conditionally use TreeSearchStage)
    - backend/pipeline/result.py (modify — add tree_data field)
    - backend/tests/test_pipeline/test_tree_search_stage.py (create)
  Depends on:       None
  Required Tests:
    | Test ID          | Type | Pass Criteria                                              |
    |:-----------------|:-----|:-----------------------------------------------------------|
    | TEST-63-01-01    | unit | TreeSearchStage activates when tree_of_thought_enabled=True|
    | TEST-63-01-02    | unit | IdeaGenerationStage used when tree_of_thought_enabled=False|
    | TEST-63-01-03    | unit | tree_data populated in PipelineResult after tree search    |
    | TEST-63-01-04    | unit | tree_data respects 500KB size limit (HB-03)                |
  Acceptance Criteria:
    AC-01-01: TreeSearchStage replaces IdeaGenerationStage when flag is on
    AC-01-02: Default pipeline unchanged when flag is off (HB-01)
    AC-01-03: Tree structure available in PipelineResult for frontend

TASK-02: BATCH-63/TASK-02 — Frontend Tree Visualization
  Description:      Create a React component that renders the search tree
                    as an interactive SVG, showing nodes (ideas), edges
                    (score transitions), and pruning decisions.
  Files in scope:
    - frontend/src/components/pipeline/tree-visualization.tsx (create)
    - frontend/src/pages/run-detail.tsx (modify — add tree tab)
    - frontend/src/components/__tests__/tree-visualization.test.tsx (create)
  Depends on:       TASK-01 (needs tree_data shape finalized)
  Required Tests:
    | Test ID          | Type | Pass Criteria                                    |
    |:-----------------|:-----|:-------------------------------------------------|
    | TEST-63-02-01    | unit | Renders tree nodes from tree_data prop            |
    | TEST-63-02-02    | unit | Shows "No tree data" message when tree_data is null|
    | TEST-63-02-03    | unit | Highlights top-scored node                        |
  Acceptance Criteria:
    AC-02-01: TreeVisualization renders interactive SVG from tree_data
    AC-02-02: Run Detail page shows tree tab when tree_data exists
    AC-02-03: No additional API calls needed (HB-02)

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Pipeline can run with tree search enabled end-to-end (mocked provider)
  BAC-02: Frontend renders tree visualization from pipeline output
  BAC-03: CHANGELOG.md updated with BATCH-63 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-63/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

Reviewer Report ID:       REVIEW-BATCH-63-2026-05-04
Review Cycle:             1
Lead Decision:            [x] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

Zero flags. Blueprint is clean.

Blueprint Version after response: 1.0 (no revision needed)
Lead Sign:                Lead (Ivory Wolf) 2026-05-04 16:36

═══════════════════════════════════════════════════════════
