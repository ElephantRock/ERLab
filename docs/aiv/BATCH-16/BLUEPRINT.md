BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-16
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead
Date Issued:              2026-05-02
Review SLA:               30 minutes
Execution SLA per Task:   60 minutes
Partial Sign-Off SLA:     15 minutes
Task Sequencing:          SEQUENTIAL (single task)

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Extend the frontend routing and navigation to support the upcoming
Phase 2 pages (costs, memory, governance, traces, sessions, literature)
by adding sidebar nav items, route definitions, and a consistent
"Coming Soon" placeholder pattern.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add sidebar nav items for: Costs, Memory, Governance, Traces, Sessions, Literature
  - Add placeholder routes in App.tsx for each new page
  - Each placeholder shows "Coming Soon" with the page title
  - Use Lucide icons consistent with existing sidebar pattern
  - Maintain existing nav items (Dashboard, Pipeline, Ideas, Gaps, Knowledge, Settings)

What the code MUST NOT do:
  - Remove or reorder existing nav items
  - Create full page implementations (placeholders only)
  - Modify any existing page components

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Existing navigation items and their routes MUST NOT change.
         New items are appended after existing ones.

  HB-02: Placeholder pages MUST NOT make API calls. They are static.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Current routes (frontend/src/App.tsx):
  / → Dashboard
  /pipeline/new → PipelineNew
  /ideas → IdeasBrowser
  /ideas/:id → IdeaDetail
  /runs/:id → RunDetail (added by BATCH-12)
  /gaps → GapsExplorer
  /knowledge → KnowledgeSearch
  /settings → Settings

Current sidebar items (frontend/src/components/layout/sidebar.tsx):
  Dashboard (LayoutDashboard), Pipeline (PlayCircle), Ideas (Lightbulb),
  Gaps (Search), Knowledge (BookOpen), Settings (Settings)

New routes and nav items:
  /costs → Placeholder "Costs" (DollarSign icon)
  /memory → Placeholder "Memory" (Brain icon)
  /governance → Placeholder "Governance" (Shield icon)
  /traces → Placeholder "Traces" (Activity icon)
  /sessions → Placeholder "Sessions" (Layers icon)
  /literature → Placeholder "Literature" (BookMarked icon)

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: Sidebar ordering: existing items first, then new items appended
         in the order listed above.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-13 (settings enhancement — nav changes must not break settings link)
  BATCH-13 status: APPROVED and closed

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,649 tests (1,519 backend + 130 frontend)
  Expected delta (all Tasks):      +10 new frontend tests
  Expected total at Batch close:   1,659

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-16/TASK-01 — Navigation Extension
  Description:      Add sidebar items and placeholder routes for all
                    Phase 2 pages, with "Coming Soon" placeholders.
  Files in scope:   frontend/src/components/layout/sidebar.tsx (MODIFY)
                    frontend/src/App.tsx (MODIFY — add routes)
                    frontend/src/pages/placeholder.tsx (NEW)
  Depends on:       None
  Required Tests:
    | Test ID          | Type | Pass Criteria                                        |
    |:-----------------|:-----|:-----------------------------------------------------|
    | TEST-16-01-01    | unit | Sidebar renders all 12 nav items (6 existing + 6 new)|
    | TEST-16-01-02    | unit | Existing nav items unchanged in order and label      |
    | TEST-16-01-03    | unit | New nav items use correct Lucide icons               |
    | TEST-16-01-04    | unit | /costs route renders placeholder with "Costs" title  |
    | TEST-16-01-05    | unit | /memory route renders placeholder                    |
    | TEST-16-01-06    | unit | /governance route renders placeholder                |
    | TEST-16-01-07    | unit | /traces route renders placeholder                    |
    | TEST-16-01-08    | unit | /sessions route renders placeholder                  |
    | TEST-16-01-09    | unit | /literature route renders placeholder                |
    | TEST-16-01-10    | unit | Placeholder pages do not make API calls              |
  Acceptance Criteria:
    AC-01-01: All 6 new sidebar items are visible and navigable
    AC-01-02: All existing nav items remain unchanged
    AC-01-03: Placeholder pages show "Coming Soon" with correct title

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: All Phase 2 pages are accessible via sidebar navigation
  BAC-02: CHANGELOG.md updated with BATCH-16 entry
  BAC-03: All documents archived under /docs/aiv/BATCH-16/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Reviewer Report ID:       REVIEW-BATCH-16-2026-05-02
Review Cycle:             1
Lead Decision:            [x] ACCEPT

CHK-07 flag noted but not acted on — icon names in Data Models are advisory.
Assistant will read actual sidebar.tsx for correct icon imports.
CHK-13 flag noted but not acted on — route integrity implicitly verified by
all existing tests continuing to pass after App.tsx modification.

Blueprint Version after response: 1.0 (unchanged)
Lead Sign:                Lead + 2026-05-02 06:55
