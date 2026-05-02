BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-20
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
Deliver a Governance Queue page showing pending approvals with
approve/deny actions and optional amendment on denial.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Replace /governance placeholder with full Governance Queue page
  - Show list of pending governance approvals
  - Approve button per item
  - Deny button with optional amendment text field
  - Real-time refresh after action

What the code MUST NOT do:
  - Modify backend governance endpoints
  - Create new backend endpoints

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: No backend modifications. Endpoints:
         GET /api/v1/governance/pending → {pending: [{id, type, summary}]}
         POST /api/v1/governance/{id}/approve → {status, decision_id}
         POST /api/v1/governance/{id}/deny → {status, decision_id, amendment}

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
  GET /governance/pending → {pending: [{id: str, type: str, summary: str}]}
  POST /governance/{id}/approve → {status: "approved", decision_id: str}
  POST /governance/{id}/deny body:{amendment?: str} → {status: "denied", decision_id, amendment}

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-16 (placeholder route)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline: 1,685 tests (1,519 backend + 168 frontend)
  Expected delta: +10 new frontend tests → 1,695

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-20/TASK-01 — Governance API Client & Components
  Files:   frontend/src/api/governance.ts (NEW)
           frontend/src/components/governance/approval-card.tsx (NEW)
  Tests:   TEST-20-01-01: getPending() calls correct endpoint
           TEST-20-01-02: approveDecision(id) calls POST approve
           TEST-20-01-03: denyDecision(id, amendment) calls POST deny
           TEST-20-01-04: ApprovalCard renders item with approve/deny buttons
           TEST-20-01-05: ApprovalCard deny opens amendment input
  Commit:  feat(batch-20/task-01): add governance API client and approval card

TASK-02: BATCH-20/TASK-02 — Governance Queue Page
  Files:   frontend/src/pages/governance.tsx (NEW — replaces placeholder)
           frontend/src/App.tsx (MODIFY — route update)
  Tests:   TEST-20-02-01: Page renders pending list
           TEST-20-02-02: Approve action removes item from list
           TEST-20-02-03: Deny with amendment removes item
           TEST-20-02-04: Empty state shows "No pending approvals"
           TEST-20-02-05: API error handled gracefully
  Commit:  feat(batch-20/task-02): add governance queue page

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Governance Queue shows pending approvals with approve/deny
  BAC-02: CHANGELOG.md updated
  BAC-03: Documents archived under /docs/aiv/BATCH-20/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Inline review: All endpoint shapes verified from governance.py source.
Blueprint version 1.0 ACCEPTED.
Lead Sign: Lead + 2026-05-02 08:25

═══════════════════════════════════════════════════════════
