```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-74
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead Programmer
Date Issued:              2026-05-05
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────

Complete the 4 remaining pipeline fixes from the "Thirteen Fixes" remediation
plan: relationship extraction for the knowledge graph (Fix #4), truth value
revision on gap-to-idea linkage (Fix #5), watchdog for stuck pipeline runs
(Fix #9), and integration test skeleton with Semantic Scholar source reordering
(Fix #10 + Fix #11b).

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────

What the code MUST do:
  - Extract CITES, USES_METHOD, EXTENDS, CONTRADICTS, BUILDS_ON, APPLIED_TO
    relationships between papers during ingestion using LLM-based extraction
  - Revise knowledge graph entity truth values upward when ideas address gaps
  - Detect and mark pipeline runs stuck in "running" status beyond a timeout
  - Provide integration tests that exercise real (non-mocked) code paths
  - Reorder academic search sources: OpenAlex first when no S2 API key

What the code MUST NOT do:
  - Make O(n²) LLM calls for relationship extraction (max 3 comparisons per paper)
  - Block or slow down the pipeline when the watchdog runs
  - Require real API keys for integration tests to pass
  - Modify any existing test files except to fix trio-mode failures

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────

  Lint command:  python -c "import ast; ast.parse(open('FILE').read())"

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────

  HB-01: Relationship extraction MUST NOT make more than 3 LLM calls per
         paper (compare each paper with at most 3 subsequent papers).
  HB-02: The watchdog MUST NOT modify runs with status != "running".
  HB-03: Integration tests MUST be marked @pytest.mark.integration and MUST
         pass without real API keys (using DummyEmbeddingProvider).
  HB-04: No existing source files may be renamed or moved.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────

RelationType enum (backend/pipeline/knowledge/relationships.py):
  CITES, USES_METHOD, EXTENDS, CONTRADICTS, BUILDS_ON, APPLIED_TO,
  IDENTIFIES_GAP, PROPOSES_METHOD

KnowledgeRelationship (backend/pipeline/knowledge/relationships.py):
  source_id: str, target_id: str, relation_type: RelationType,
  weight: float, evidence: list[str], truth: TruthValue

TruthValue (backend/pipeline/knowledge/truth.py):
  frequency: float, confidence: float, evidence_count: int,
  propagation_debt: float
  Methods: revise(), decay(), settle_debt(), from_observation(), initial()

PipelineRun (backend/db/models.py):
  id, status, domain, config_json, error_message, session_id,
  current_stage, stages_completed, cluster_report_json, tree_data_json,
  ideas (relationship), gaps (relationship), created_at, completed_at
  NEW: updated_at: datetime (nullable, auto-set on stage advance)

alembic/versions/006_watchdog_updated_at.py:
  ADD COLUMN updated_at DATETIME NULL to pipeline_runs

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────

  - Only the watchdog may change run status from "running" to "failed"
    for stale runs. Normal pipeline execution changes it to "completed".
  - Truth revision may only increase confidence (capped at 0.99), never decrease.
  - Relationship extraction confidence must be ≥0.5 to be persisted.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────

  - BATCH-73 (commit 8552dba): Vector store fix, proposal synthesizer rewrite,
    pipeline stages fixes. Must not be reverted.
  - backend/pipeline/knowledge/relationships.py: RelationType enum (exists)
  - backend/pipeline/knowledge/truth.py: TruthValue.revise() (exists)
  - backend/pipeline/execution/heartbeat.py: StageHeartbeat (exists)
  - backend/db/models.py: PipelineRun model (exists, needs updated_at)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────

  Baseline at Blueprint issuance:  1,595 passing tests (5 pre-existing trio failures)
  Expected delta (all Tasks):      +25 new tests
  Expected total at Batch close:   ~1,620

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-74/TASK-01 — Knowledge Graph Relationship Extraction (Fix #4)
  Description:      Create relationship_extractor.py to extract CITES, USES_METHOD,
                    EXTENDS, CONTRADICTS, BUILDS_ON, APPLIED_TO relationships between
                    papers during ingestion. Integrate into IngestionStage.
  Files in scope:
    - backend/pipeline/knowledge/relationship_extractor.py (NEW)
    - backend/pipeline/stages.py (MODIFY — IngestionStage.execute)
    - backend/tests/test_pipeline/test_relationship_extraction.py (NEW)
  Depends on:       None
  Required Tests:
    | Test ID          | Type   | Pass Criteria                                         |
    |:-----------------|:-------|:------------------------------------------------------|
    | TEST-74-01-01    | unit   | extract_relationships returns CITES relationship      |
    | TEST-74-01-02    | unit   | extract_relationships returns EXTENDS relationship    |
    | TEST-74-01-03    | unit   | extract_relationships skips when <2 papers            |
    | TEST-74-01-04    | unit   | extract_relationships respects 3-comparison limit     |
    | TEST-74-01-05    | unit   | IngestionStage calls relationship extraction          |
  Acceptance Criteria:
    AC-01-01: relationship_extractor.py exists and passes ast.parse
    AC-01-02: IngestionStage.execute calls extract_relationships after entity creation
    AC-01-03: No more than 3 LLM calls per paper (HB-01)

TASK-02: BATCH-74/TASK-02 — Truth Value Revision (Fix #5)
  Description:      Revise gap truth values upward when ideas reference them.
                    Also revise when papers relate to gaps by keyword overlap.
  Files in scope:
    - backend/pipeline/stages.py (MODIFY — IdeaGenerationStage)
  Depends on:       TASK-01 (relationship extraction enriches KG context)
  Required Tests:
    | Test ID          | Type   | Pass Criteria                                         |
    |:-----------------|:-------|:------------------------------------------------------|
    | TEST-74-02-01    | unit   | Gap truth confidence increases after idea generation  |
    | TEST-74-02-02    | unit   | TruthValue.evidence_count increases after revision    |
    | TEST-74-02-03    | unit   | Truth confidence never exceeds 0.99                   |
  Acceptance Criteria:
    AC-02-01: idea generation stage calls truth.revise() on referenced gaps
    AC-02-02: Gap confidence increases from initial 0.5

TASK-03: BATCH-74/TASK-03 — Pipeline Run Watchdog (Fix #9)
  Description:      Create watchdog.py to detect and mark stale pipeline runs.
                    Add updated_at column to PipelineRun. Add API endpoint.
  Files in scope:
    - backend/pipeline/execution/watchdog.py (NEW)
    - backend/db/models.py (MODIFY — PipelineRun.updated_at)
    - alembic/versions/006_watchdog_updated_at.py (NEW)
    - backend/pipeline/persistence.py (MODIFY — find_stale_runs, advance_stage)
    - backend/api/routes/pipeline.py (MODIFY — watchdog endpoint)
    - backend/tests/test_pipeline/test_watchdog.py (NEW)
  Depends on:       None
  Required Tests:
    | Test ID          | Type   | Pass Criteria                                         |
    |:-----------------|:-------|:------------------------------------------------------|
    | TEST-74-03-01    | unit   | find_stale_runs returns runs past timeout             |
    | TEST-74-03-02    | unit   | find_stale_runs ignores completed runs (HB-02)        |
    | TEST-74-03-03    | unit   | watchdog marks stale run as failed                    |
    | TEST-74-03-04    | unit   | advance_stage updates updated_at timestamp            |
    | TEST-74-03-05    | unit   | POST /pipeline/watchdog returns cleaned count         |
    | TEST-74-03-06    | unit   | migration 006 adds updated_at column                  |
  Acceptance Criteria:
    AC-03-01: watchdog.py exists and passes ast.parse
    AC-03-02: find_stale_runs only returns status="running" (HB-02)
    AC-03-03: advance_stage updates updated_at on PipelineRun

TASK-04: BATCH-74/TASK-04 — Integration Tests + Source Reordering (Fix #10 + #11b)
  Description:      Create integration test skeleton with ≥3 tests. Reorder
                    academic search sources to put OpenAlex first when no S2 key.
  Files in scope:
    - backend/tests/integration/__init__.py (NEW)
    - backend/tests/integration/test_pipeline_smoke.py (NEW)
    - backend/pipeline/literature/search_service.py (MODIFY — _default_sources)
    - backend/tests/test_pipeline/test_source_reordering.py (NEW)
  Depends on:       TASK-03 (watchdog tests may be referenced in smoke tests)
  Required Tests:
    | Test ID          | Type        | Pass Criteria                                    |
    |:-----------------|:------------|:-------------------------------------------------|
    | TEST-74-04-01    | integration | Pipeline can start and not crash                  |
    | TEST-74-04-02    | integration | Embedding service returns non-zero vectors        |
    | TEST-74-04-03    | integration | Vector store dimension matches embedding dim      |
    | TEST-74-04-04    | unit        | OpenAlex is first when no S2 API key              |
    | TEST-74-04-05    | unit        | S2 is first when API key is present               |
  Acceptance Criteria:
    AC-04-01: test_pipeline_smoke.py exists with ≥3 integration tests (HB-03)
    AC-04-02: All integration tests pass with DummyEmbeddingProvider (HB-03)
    AC-04-03: OpenAlex is first source when semantic_scholar_api_key is None

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────

  BAC-01: All 4 Tasks have APPROVED Partial Sign-Offs.
  BAC-02: Total test count ≥ 1,620 (baseline 1,595 + ≥25 new).
  BAC-03: CHANGELOG.md updated with BATCH-74 entry.
  BAC-04: All documents archived under /docs/aiv/BATCH-74/.

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

Reviewer Report ID:       REVIEW-BATCH-74-2026-05-05
Review Cycle:             1
Lead Decision:            [X] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

No flags raised. Blueprint approved as-is.

Blueprint Version after response: 1.0
Lead Sign:                Lead Programmer — 2026-05-05 12:01

═══════════════════════════════════════════════════════════
```
