# BATCH BLUEPRINT — BATCH-175

Batch ID:                 BATCH-175
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-11
Review SLA:               30 min
Execution SLA per Task:   90 min
Partial Sign-Off SLA:     15 min
Task Sequencing: Sequential

---

## BATCH GOAL

Write a single integration test that creates a `PipelineOrchestrator` with all
providers and services mocked, calls `orchestrator.run(domain="test")`, and verifies
all 16 stages execute in order, the result contains papers/gaps/ideas/proposals,
and the `stage_report` shows 16 entries with meaningful status. This test becomes
the canonical wiring verification — if any stage is dead-coded or unwired, it fails.

---

## SCOPE STATEMENT

**What the code MUST do:**
- Create a comprehensive mock setup that replaces all external dependencies (LLM provider, embedding service, vector store, search service, database) with deterministic mocks
- Write one test that calls `PipelineOrchestrator.__init__()` with mocked settings and then `orchestrator.run(domain="test_domain")`
- Verify all 16 stages appear in `result.stage_report`
- Verify at least `literature_search`, `ingestion`, `gap_analysis`, `idea_generation` have status `"executed"` (not `"skipped_by_error"` or `"not_reached"`)
- Verify `result.papers_found > 0`, `len(result.gaps) > 0`, `len(result.ideas) > 0`, `len(result.proposals) > 0`
- Verify stages execute in `_STAGE_ORDER` sequence

**What the code MUST NOT do:**
- MUST NOT modify the orchestrator or any stage implementation
- MUST NOT require running services (LM Studio, database, internet)
- MUST NOT use real LLM calls — all providers must be mocked

---

## LINT COMMAND

```
python -m pytest backend/tests/test_pipeline/test_batch175_*.py -v --tb=short -p no:asyncio
```

---

## HARD BOUNDARIES

- **HB-01**: The test must instantiate a real `PipelineOrchestrator` (not mock it) and call its actual `run()` method. Only external dependencies are mocked.
- **HB-02**: The test must pass without any running services (no LM Studio, no database server, no internet).
- **HB-03**: If any of the 16 stages is unwired or dead-coded, the test must FAIL (not pass silently).

---

## DATA MODELS / SCHEMA

**New test file:**
- `backend/tests/test_pipeline/test_batch175_e2e_integration.py` — TASK-01 + TASK-02

**Key dependencies to mock (read from orchestrator.__init__):**
- `backend.config.get_settings()` → return mock Settings with all required fields
- `backend.providers.provider_factory.create_provider()` → return mock LLM provider
- `backend.providers.provider_factory.get_thinking_provider()` → return mock thinking provider
- `backend.pipeline.knowledge.vector_store.VectorStore` → return mock with `.count()` returning 0
- `backend.pipeline.literature.search_service.SearchService` → return mock returning test papers
- `backend.pipeline.knowledge.embedding_service.EmbeddingService` → return mock
- `backend.db.database.SessionLocal` → return mock DB session
- `backend.pipeline.persistence.PersistenceService` → return mock

**Orchestrator constructor flow** (from reading orchestrator.py lines 120-190):
1. Stores settings, creates services via `_init_core_services(settings)`
2. `_init_core_services` creates: provider, embedding, vector store, search service, BM25, knowledge graph, agent, synthesizer, novelty checker, feasibility scorer, etc.
3. `_build_stages()` creates 16 stage instances using these services
4. The test must mock at the right level — either mock `_init_core_services` to inject services, or mock individual service factories

**Best approach**: Subclass `PipelineOrchestrator` in the test, override `_init_core_services` to inject all mock services, then call `run()` on the real orchestrator with real stage execution.

---

## AUTHORITY RULES

- **AUTH-01**: The test must use `asyncio.run(orchestrator.run(...))` — not `@pytest.mark.asyncio`
- **AUTH-02**: Mock LLM responses must be deterministic — same input always produces same output
- **AUTH-03**: If the test takes longer than 60 seconds to execute, it must be marked with a timeout or the mock responses must be simplified

---

## DEPENDENCY MAP

- BATCH-172 (wired stages) — CLOSED
- BATCH-173 (stage_report) — CLOSED
- BATCH-174 (functional tests demonstrate mock patterns) — CLOSED
- `backend/pipeline/orchestrator.py` — READ ONLY
- `backend/pipeline/stages.py` — READ ONLY

---

## STATE.md STATUS

- State file exists: YES
- Last Updated: 2026-05-11 (BATCH-174)
- Batches since update: 0
- Reconciliation audit: N/A

---

## TEST BASELINE

- Baseline at Blueprint issuance: **2,815** tests
- Expected delta (all Tasks): **+8** new tests
- Expected total at Batch close: **2,823**

---

## TASK LIST

### TASK-01: BATCH-175/TASK-01 — Mock Infrastructure + Full Pipeline Run
- **Priority:** Critical
- **Description:** Build the mock infrastructure for a full pipeline run. Create a test that instantiates PipelineOrchestrator with all mocked services and runs the full 16-stage pipeline. Verify all stages execute and produce output.
- **Files in scope:** NEW FILE `backend/tests/test_pipeline/test_batch175_e2e_integration.py`
- **Depends on:** None

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-175-01-01 | integration | Full pipeline run completes without error | Stage crash | Unwire a stage | `result` is not None, no unhandled exception |
| TEST-175-01-02 | integration | All 16 stages in stage_report | Missing stage | Remove stage from _build_stages | `len(result.stage_report) == 16` |
| TEST-175-01-03 | integration | Core stages have "executed" status | Dead stage | Set stage to skip | At least literature_search, ingestion, gap_analysis, idea_generation are "executed" |
| TEST-175-01-04 | integration | Result has papers | No papers found | Mock returns empty | `result.papers_found > 0` |
| TEST-175-01-05 | integration | Result has gaps | No gaps | Mock returns empty | `len(result.gaps) > 0` |
| TEST-175-01-06 | integration | Result has ideas | No ideas | Mock returns empty | `len(result.ideas) > 0` |
| TEST-175-01-07 | integration | Result has proposals | No proposals | Mock returns empty | `len(result.proposals) > 0` or proposals stage skipped with documented reason |

**Acceptance Criteria:**
- AC-01-01: One test runs the full pipeline with all providers mocked
- AC-01-02: All 16 stages appear in stage_report
- AC-01-03: Core stages (0-4) execute successfully
- AC-01-04: Result contains papers, gaps, ideas

**Traceability:** AC-01-01→T-01 | AC-01-02→T-02 | AC-01-03→T-03 | AC-01-04→T-04,T-05,T-06

---

### TASK-02: BATCH-175/TASK-02 — Stage Ordering + Regression + Batch Close
- **Priority:** High
- **Description:** Add a test verifying stages execute in correct order. Verify no regressions. Update STATE.md and CHANGELOG.
- **Files in scope:** Same file + `docs/aiv/STATE.md` + `CHANGELOG.md`
- **Depends on:** TASK-01

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-175-02-01 | integration | Stages execute in _STAGE_ORDER | Wrong order | Swap stage positions | `report[i].name == _STAGE_ORDER[i]` for all i |
| TEST-175-02-02 | integration | No regressions in batch172-174 | Regression | Revert wiring | subprocess check passes |
| TEST-175-02-03 | unit | STATE.md has BATCH-175 | Stale state | Check content | `"BATCH-175" in content` |
| TEST-175-02-04 | unit | CHANGELOG has BATCH-175 | Missing trail | Check content | `"BATCH-175" in content` |

**Acceptance Criteria:**
- AC-02-01: Stage order test passes
- AC-02-02: No regressions
- AC-02-03: STATE.md and CHANGELOG updated

**Traceability:** AC-02-01→T-01 | AC-02-02→T-02 | AC-02-03→T-03,T-04

---

## BATCH-LEVEL ACCEPTANCE CRITERIA

- **BAC-01**: Full pipeline E2E test runs with all 16 stages mocked
- **BAC-02**: All 16 stages appear in stage_report
- **BAC-03**: Stages execute in _STAGE_ORDER
- **BAC-04**: No regressions in batch172-174
- **BAC-05**: CHANGELOG.md updated
- **BAC-06**: All documents archived under `/docs/aiv/BATCH-175/`

---

## LEAD RESPONSE TO REVIEW REPORT

[Leave blank until Review Report received.]
