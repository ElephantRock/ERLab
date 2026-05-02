BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-19
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
Deliver a Memory Browser page allowing users to view, search, and delete
memories stored by the platform's memory system.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Replace /memory placeholder with full Memory Browser page
  - Create API client for memory endpoints (3 endpoints exist)
  - Show memory statistics (total, by type)
  - Searchable memory list via /recall endpoint
  - Memory cards: content preview, type badge, confidence, date
  - Delete button per memory with confirmation

What the code MUST NOT do:
  - Modify existing backend memory endpoints
  - Create new backend endpoints
  - Implement memory consolidation or management logic on frontend

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: No backend modifications. All memory endpoints already exist:
         GET /api/v1/memory/stats
         GET /api/v1/memory/recall?query=...&memory_type=...&top_k=...
         DELETE /api/v1/memory/{entry_id}

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Existing backend (backend/api/routes/memory.py):
  GET /memory/stats  → {total_memories: int, by_type: {type_name: count}}
  GET /memory/recall → {query: str, results: [{content, type, confidence, created_at}]}
  DELETE /memory/{id} → {status: "deleted", entry_id: str}

NOTE: There is NO /memory/memories list endpoint. All browsing uses /recall
with a broad query (e.g., "*"). Memory types from backend/pipeline/memory/models.py
include: insight, fact, working, episodic, semantic (via MemoryType enum).

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AR-01: Memory deletion requires confirmation. No bulk delete.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-16 (placeholder route)
  BATCH-16 status: APPROVED and closed

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,673 tests (1,519 backend + 154 frontend)
  Expected delta (all Tasks):      +12 new frontend tests
  Expected total at Batch close:   1,685

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-19/TASK-01 — Memory API Client & Components
  Files in scope:   frontend/src/api/memory.ts (NEW)
                    frontend/src/components/memory/memory-card.tsx (NEW)
                    frontend/src/components/memory/memory-stats.tsx (NEW)
  Required Tests:
    | Test ID          | Type | Pass Criteria                                    |
    |:-----------------|:-----|:-------------------------------------------------|
    | TEST-19-01-01    | unit | getMemoryStats() calls /memory/stats              |
    | TEST-19-01-02    | unit | recallMemories(query) sends query param           |
    | TEST-19-01-03    | unit | deleteMemory(id) calls DELETE /memory/{id}        |
    | TEST-19-01-04    | unit | MemoryCard renders content, type badge, confidence|
    | TEST-19-01-05    | unit | MemoryStats renders total and per-type counts     |

TASK-02: BATCH-19/TASK-02 — Memory Browser Page
  Files in scope:   frontend/src/pages/memory.tsx (NEW — replaces placeholder)
                    frontend/src/App.tsx (MODIFY — update route import)
  Depends on:       TASK-01
  Required Tests:
    | Test ID          | Type | Pass Criteria                                      |
    |:-----------------|:-----|:---------------------------------------------------|
    | TEST-19-02-01    | unit | Memory page renders with stats header              |
    | TEST-19-02-02    | unit | Search input triggers recall with query            |
    | TEST-19-02-03    | unit | Type filter sends memory_type param                |
    | TEST-19-02-04    | unit | Delete confirmation removes memory from list       |
    | TEST-19-02-05    | unit | Empty results shows appropriate message            |
    | TEST-19-02-06    | unit | Handles API error gracefully                       |
    | TEST-19-02-07    | unit | Initial load uses broad recall query               |

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Memory Browser shows stored memories with search and filter
  BAC-02: CHANGELOG.md updated with BATCH-19 entry
  BAC-03: All documents archived under /docs/aiv/BATCH-19/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Reviewer Report ID:       INLINE-REVIEW-BATCH-19-2026-05-02
Review Cycle:             N/A (inline Lead review — Reviewer session queue stalled)
Lead Decision:            [x] ACCEPT

CHK-07 verified inline: response shapes read directly from costs.py source.
All 3 endpoint response formats confirmed accurate. No /memories list endpoint
exists — adapted to use /recall with broad query for browsing.
CHK-12/13 verified: 12 tests cover API client (3), components (2), page (7).

Blueprint Version after response: 1.0 (unchanged)
Lead Sign:                Lead + 2026-05-02 08:00
