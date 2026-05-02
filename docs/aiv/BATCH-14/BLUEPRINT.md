BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-14
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead
Date Issued:              2026-05-02
Review SLA:               30 minutes
Execution SLA per Task:   90 minutes
Partial Sign-Off SLA:     15 minutes
Task Sequencing:          SEQUENTIAL

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Transform the Ideas Browser from a static list into a sortable, filterable,
searchable interface, and establish bidirectional traceability between
research gaps and generated ideas.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add sort dropdown to Ideas Browser (score, novelty, feasibility, date)
  - Add min_score slider filter (0.0-1.0)
  - Add search input for full-text keyword search on title
  - Show overall score badge on IdeaCard
  - Add proposal indicator icon on cards with existing proposals
  - Backend: add search and sort params to GET /ideas
  - Backend: add idea count per gap in gap responses
  - Backend: include pipeline_run_id in idea responses
  - Frontend: GapCard shows "N ideas generated" badge
  - Frontend: Idea Detail shows source gaps section

What the code MUST NOT do:
  - Remove existing pagination on Ideas Browser
  - Change the gap scoring or idea scoring algorithms
  - Modify the knowledge graph data model

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Full-text search on ideas MUST use parameterized queries only.
         No string interpolation into SQL. SQL injection is a hard boundary.

  HB-02: The idea scoring algorithm MUST NOT be altered. Only display
         and sorting of existing scores is in scope.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Existing (backend/db/models.py — verified in BATCH-12):
  class Idea:
    id: int, title: str, problem_statement: str, proposed_method: str,
    expected_contributions: str, domain: str,
    novelty_score: float | None, feasibility_score: float | None,
    overall_score: float | None, novelty_report: str | None,
    feasibility_report: str | None, user_rating: int | None,
    user_notes: str | None, pipeline_run_id: int | None (FK),
    proposal: relationship → Proposal | None, created_at: datetime

    NOTE: source_gap_ids exists in the pipeline Pydantic model
    (backend/pipeline/generation/models.py: ResearchIdea.source_gap_ids)
    but NOT in the SQLAlchemy Idea model. TASK-01 will add it as a
    JSON Text column to the Idea DB model.

  class ResearchGapDB:
    id: int, title: str, description: str, gap_type: str,
    confidence: float, potential_impact: str,
    pipeline_run_id: int | None (FK), created_at: datetime

  class Proposal:
    id: int, idea_id: int (FK, unique), content_md: str,
    content_latex: str | None, references_json: str, sections_json: str | None

Gap↔Idea traceability mechanism:
  1. Add source_gap_ids: str (JSON Text) to the Idea SQLAlchemy model
  2. Populate it during pipeline persistence (stages.py line ~319 already
     iterates idea.source_gap_ids)
  3. Backend queries use JSON parsing to count ideas per gap
  4. Historical ideas (pre-BATCH-14) will have null source_gap_ids

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: Search and sort are backend concerns. The frontend passes params;
         the backend performs the query. No client-side filtering of large sets.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-12 (ideas display components used from pipeline results)
  BATCH-12 status: APPROVED and closed

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,627 tests (1,513 backend + 114 frontend)
  Expected delta (all Tasks):      +17 new tests (10 backend + 7 frontend)
  Expected total at Batch close:   1,644

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-14/TASK-01 — Backend: Sort, Search, Traceability
  Description:      Add search/sort query parameters to the ideas endpoint,
                    add source_gap_ids column to the Idea DB model,
                    add idea count per gap in gap responses, and wire up
                    gap↔idea traceability.
  Files in scope:   backend/api/routes/ideas.py (MODIFY)
                    backend/api/routes/gaps.py (MODIFY)
                    backend/db/crud.py (MODIFY)
                    backend/db/models.py (MODIFY — add source_gap_ids column)
                    backend/pipeline/stages.py (MODIFY — persist source_gap_ids)
  Depends on:       None
  Required Tests:
    | Test ID          | Type        | Pass Criteria                                    |
    |:-----------------|:------------|:-------------------------------------------------|
    | TEST-14-01-01    | unit        | search param filters ideas by title keyword       |
    | TEST-14-01-02    | unit        | sort_by=score returns ideas ordered by score desc |
    | TEST-14-01-03    | unit        | min_score=0.7 returns only ideas ≥ 0.7            |
    | TEST-14-01-04    | unit        | count_ideas_for_gap returns correct count         |
    | TEST-14-01-05    | integration | GET /ideas?search=test returns matching ideas     |
    | TEST-14-01-06    | integration | GET /gaps includes idea_count field               |
    | TEST-14-01-07    | unit        | SQL injection treated as literal string (parameterized) |
    | TEST-14-01-08    | unit        | sort_by accepts score/novelty/feasibility/date    |
    | TEST-14-01-09    | unit        | source_gap_ids persisted on Idea model             |
    | TEST-14-01-10    | unit        | null/empty score handled in sort (nulls last)     |
  Acceptance Criteria:
    AC-01-01: Ideas can be sorted by score, novelty, feasibility, date
    AC-01-02: Full-text search works on title field using parameterized queries
    AC-01-03: Gap responses include idea count
    AC-01-04: SQL injection is impossible (parameterized queries only)

TASK-02: BATCH-14/TASK-02 — Frontend: Ideas & Gaps UX
  Description:      Enhance Ideas Browser with sort/filter/search UI,
                    add score badges to IdeaCards, add proposal indicator,
                    enhance GapCard with idea count badge, and show gap
                    context on Idea Detail where traceability exists.
  Files in scope:   frontend/src/pages/ideas-browser.tsx (MODIFY)
                    frontend/src/pages/idea-detail.tsx (MODIFY)
                    frontend/src/pages/gaps-explorer.tsx (MODIFY)
                    frontend/src/components/ideas/idea-card.tsx (MODIFY)
                    frontend/src/components/gaps/gap-card.tsx (MODIFY)
                    frontend/src/api/ideas.ts (MODIFY — add params)
  Depends on:       TASK-01 (needs backend endpoint changes)
  Required Tests:
    | Test ID          | Type | Pass Criteria                                      |
    |:-----------------|:-----|:---------------------------------------------------|
    | TEST-14-02-01    | unit | Sort dropdown renders with 4 options               |
    | TEST-14-02-02    | unit | Min score slider renders with 0-1 range            |
    | TEST-14-02-03    | unit | Search input filters ideas by keyword              |
    | TEST-14-02-04    | unit | IdeaCard shows overall score badge                 |
    | TEST-14-02-05    | unit | IdeaCard shows proposal icon when proposal exists  |
    | TEST-14-02-06    | unit | GapCard shows "N ideas generated" badge            |
    | TEST-14-02-07    | unit | GapCard badge click navigates to filtered ideas    |
  Acceptance Criteria:
    AC-02-01: User can sort ideas by any score dimension
    AC-02-02: Min score filter works in real-time
    AC-02-03: Bidirectional gap↔idea navigation works where data supports it

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Ideas Browser is sortable, filterable, and searchable
  BAC-02: Gap↔Idea traceability works in both directions
  BAC-03: CHANGELOG.md updated with BATCH-14 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-14/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Reviewer Report ID:       REVIEW-BATCH-14-2026-05-02
Review Cycle:             1
Lead Decision:            [x] ACCEPT WITH MODIFICATIONS

FLAG-01 (CHK-13): Acted on — added TEST-14-01-10 for null score handling
  in sort. Combined params and sort direction tested implicitly via
  integration tests. Error states on frontend accepted as low severity.
FLAG-02 (CHK-14): Confirmed — 1,627 tests verified: 1,513 backend +
  114 frontend (after BATCH-13 closure).
FLAG-03 (CHK-16): Acted on — resolved traceability mechanism. Adding
  source_gap_ids as JSON Text column to Idea DB model. TASK-01 files-in-scope
  expanded to include models.py and stages.py. Added TEST-14-01-09.
  Historical ideas will have null source_gap_ids (acceptable).
FLAG-04 (CHK-17): Acted on — (a) search param is additive to existing
  filters (documented in route decorator). (b) removed "include
  pipeline_run_id" from scope (already implemented). (c) corrected
  TEST-14-01-07 pass criteria to "treated as literal string."

Blueprint Version after response: 1.1
Lead Sign:                Lead + 2026-05-02 06:10
