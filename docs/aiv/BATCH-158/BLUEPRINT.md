BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-158
Blueprint Version:        1.0 (Lead-Reviewed, Direct Implementation)
Cycle Mode:               STANDARD (§5.3 Lead Override)

BATCH GOAL
───────────────────────────────────────────────────────────
Wire existing KnowledgeLibrary + LibraryIndexer into pipeline.
Post-run: index papers/gaps/ideas into SQLite library.
Pre-run: query existing knowledge to inform search.

HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: All 2,591 pre-existing tests pass.
  HB-02: Library failure MUST NOT block pipeline. All ops are fail-safe.
  HB-03: SQLite DB at data/knowledge_library.db. Created on first use.

TASKS
───────────────────────────────────────────────────────────
TASK-01: Post-run indexing in ExportStage (7 tests)
  - After export, index papers/gaps/ideas into KnowledgeLibrary
  - Log counts

TASK-02: Pre-run knowledge query in LiteratureSearchStage (5 tests)
  - Before searching, query existing papers for the domain
  - Merge into search results (dedup)
  - Log how many pre-existing papers were found

TASK-03: Knowledge query API endpoint (2 tests)
  - GET /api/v1/knowledge/{domain} → returns existing papers/gaps/ideas
  - Uses existing KnowledgeIntegrationService

TEST BASELINE: 2,591 → 2,605 (+14)
═══════════════════════════════════════════════════════════
