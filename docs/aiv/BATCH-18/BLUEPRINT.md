BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-18
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
Deliver a Cost Dashboard page showing total spend, cost breakdowns by
provider/stage/model, per-run costs, and budget utilization.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Replace /costs placeholder with full Cost Dashboard page
  - Create API client for cost endpoints (5 endpoints already exist in backend)
  - Show total spend summary
  - Cost by provider (table), by stage (table), by model (table)
  - Per-run cost breakdown
  - Budget utilization bar (current vs configured limit)

What the code MUST NOT do:
  - Modify existing backend cost endpoints or cost tracking logic
  - Create new backend endpoints (all cost data is already available)
  - Store cost data on the frontend

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: No backend modifications. All cost endpoints already exist:
         GET /api/v1/costs/summary
         GET /api/v1/costs/by-provider
         GET /api/v1/costs/by-stage
         GET /api/v1/costs/by-model
         GET /api/v1/costs/runs/{id}

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Existing backend endpoints (backend/api/routes/costs.py):
  GET /costs/summary     → {total_cost_usd: float, total_tokens: int, event_count: int}
  GET /costs/by-provider → {provider_name: {cost_usd, input_tokens, output_tokens, calls}}
  GET /costs/by-stage    → {stage_name: {cost_usd, input_tokens, output_tokens, calls}}
  GET /costs/by-model    → {model_name: {cost_usd, input_tokens, output_tokens, calls}}
  GET /costs/run/{id}    → {run_id, summary: {...}, by_provider: {...}, by_stage: {...}}

  NOTE: by-provider, by-stage, by-model return DICTS (not arrays).
  The frontend must iterate Object.entries() to render tables.

Router prefix: /api/v1/costs (registered in app.py)

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: Cost data is read-only from the frontend perspective.
         No cost manipulation endpoints are called.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-16 (placeholder route must exist)
  BATCH-16 status: APPROVED and closed

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,659 tests (1,519 backend + 140 frontend)
  Expected delta (all Tasks):      +14 new frontend tests
  Expected total at Batch close:   1,673

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-18/TASK-01 — Cost API Client
  Description:      Create frontend API client module for the existing
                    cost endpoints.
  Files in scope:   frontend/src/api/costs.ts (NEW)
  Depends on:       None
  Required Tests:
    | Test ID          | Type | Pass Criteria                                   |
    |:-----------------|:-----|:------------------------------------------------|
    | TEST-18-01-01    | unit | getCostSummary() calls correct endpoint          |
    | TEST-18-01-02    | unit | getCostByProvider() returns typed response       |
    | TEST-18-01-03    | unit | getCostByStage() returns typed response          |
    | TEST-18-01-04    | unit | getCostByModel() returns typed response          |
    | TEST-18-01-05    | unit | getRunCostBreakdown(id) calls /costs/run/{id}    |
  Acceptance Criteria:
    AC-01-01: All 5 cost API functions work with correct types

TASK-02: BATCH-18/TASK-02 — Cost Components
  Description:      Create chart/table components for cost visualization.
  Files in scope:   frontend/src/components/costs/cost-summary-card.tsx (NEW)
                    frontend/src/components/costs/cost-breakdown-table.tsx (NEW)
                    frontend/src/components/costs/budget-bar.tsx (NEW)
  Depends on:       TASK-01
  Required Tests:
    | Test ID          | Type | Pass Criteria                                        |
    |:-----------------|:-----|:-----------------------------------------------------|
    | TEST-18-02-01    | unit | CostSummaryCard renders total cost and token counts   |
    | TEST-18-02-02    | unit | CostBreakdownTable renders rows from data             |
    | TEST-18-02-03    | unit | BudgetBar renders utilization percentage              |
  Acceptance Criteria:
    AC-02-01: Components render correctly with cost data
    AC-02-02: Components show appropriate empty states

TASK-03: BATCH-18/TASK-03 — Cost Dashboard Page
  Description:      Replace placeholder with full Cost Dashboard page.
  Files in scope:   frontend/src/pages/costs.tsx (NEW — replaces placeholder)
                    frontend/src/App.tsx (MODIFY — update route import)
  Depends on:       TASK-02
  Required Tests:
    | Test ID          | Type | Pass Criteria                                      |
    |:-----------------|:-----|:---------------------------------------------------|
    | TEST-18-03-01    | unit | Cost dashboard renders without crashing            |
    | TEST-18-03-02    | unit | Shows cost summary section                         |
    | TEST-18-03-03    | unit | Shows breakdown tables (provider/stage/model)      |
    | TEST-18-03-04    | unit | Shows per-run cost list                            |
    | TEST-18-03-05    | unit | Shows budget utilization bar                       |
    | TEST-18-03-06    | unit | Handles API error gracefully                       |
  Acceptance Criteria:
    AC-03-01: User can see total cost at a glance
    AC-03-02: Costs broken down by provider, stage, and model
    AC-03-03: Budget limits are visualized

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Cost Dashboard shows complete cost breakdown
  BAC-02: CHANGELOG.md updated with BATCH-18 entry
  BAC-03: All documents archived under /docs/aiv/BATCH-18/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Reviewer Report ID:       REVIEW-BATCH-18-2026-05-02
Review Cycle:             1
Lead Decision:            [x] ACCEPT WITH MODIFICATIONS

FLAG-01 (CHK-07): ACTED ON — Data Models corrected. by-provider/stage/model
return dicts not arrays. Endpoint paths corrected (/costs/run/{id} not /runs/{id}).
Field names corrected (cost_usd not total_cost_usd for breakdowns, event_count not total_requests).
FLAG-02 (CHK-12): Not acted on — LOW severity. Empty states implicitly tested by rendering.
FLAG-03 (CHK-13): Not acted on — LOW severity. TEST-18-03-06 covers API error at page level.
FLAG-04 (CHK-14): Not acted on — baseline counts are approximate. Delta (+14) is authoritative.

Blueprint Version after response: 1.1
Lead Sign:                Lead + 2026-05-02 07:45
