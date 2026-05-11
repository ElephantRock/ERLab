# BLUEPRINT REVIEW REPORT — BATCH-175

| Field | Value |
|:------|:------|
| Batch ID | BATCH-175 |
| Blueprint Version | 1.0 |
| Reviewer | Craft Agent (Blueprint Reviewer, AIV v5.3) |
| Date Reviewed | 2026-05-11 |
| Verdict | **CONDITIONAL PASS — 5 Findings (2 Major, 3 Minor)** |
| Lead Response Due | Per SLA: 30 min from issuance |

---

## CHK-00: Cycle Mode

**Result:** ✅ PASS

Blueprint declares `Cycle Mode: STANDARD`. This is consistent with the scope (new test file, no source modifications). No FAST-TRACK indicators present; no MICROCYLE justification needed. STANDARD is correct for a multi-task batch with external mock infrastructure.

---

## CHK-01: Batch ID

**Result:** ✅ PASS

`BATCH-175` follows the sequential scheme. STATE.md last recorded batch is BATCH-174. No gap in sequence. ID is well-formed.

---

## CHK-02: SLAs

**Result:** ✅ PASS

| SLA | Value | Assessment |
|:----|:------|:-----------|
| Review SLA | 30 min | Standard. Acceptable. |
| Execution SLA per Task | 90 min | TASK-01 (mock infra + full pipeline) is ambitious for 90 min given the 19 `_init_*` methods to mock, but achievable. |
| Partial Sign-Off SLA | 15 min | Standard. |

---

## CHK-03: Goal

**Result:** ✅ PASS

Goal is specific and testable: *"Write a single integration test that creates a `PipelineOrchestrator` with all providers and services mocked, calls `orchestrator.run(domain="test")`, and verifies all 16 stages execute in order."* Directly maps to TASK-01 and TASK-02. Goal is atomic and falsifiable.

---

## CHK-04: Scope Statement

**Result:** ✅ PASS

**MUST do** is precise: mock setup, one test, 16-stage verification, output assertions. **MUST NOT do** is equally clear: no orchestrator modifications, no running services, no real LLM calls. Boundaries are unambiguous.

---

## CHK-05: Acceptance Criteria

**Result:** ✅ PASS

BAC-01 through BAC-06 are all testable:
- BAC-01 (full pipeline E2E with mocks) → falsifiable by unwiring a mock
- BAC-02 (16 stages in report) → countable
- BAC-03 (stage order) → ordinal comparison
- BAC-04 (no regressions) → subprocess check
- BAC-05 (CHANGELOG) → content check
- BAC-06 (docs archived) → file existence

---

## CHK-06: Hard Boundaries

**Result:** ✅ PASS

| HB | Description | Verifiable? |
|:---|:------------|:------------|
| HB-01 | Real orchestrator, only externals mocked | Yes — import check |
| HB-02 | No running services | Yes — no network calls in mocks |
| HB-03 | Fails if stage is unwired | Yes — test will assert 16 stages |

All three are enforceable through the test itself. HB-03 is the key value proposition.

---

## CHK-07: Data Models / Schema

**Result:** ⚠️ **FINDING F-01 (Major)**

The blueprint's DATA MODELS section describes mock targets but contains a **critical type mismatch**:

- Blueprint says: `len(result.proposals) > 0`
- Actual type: `proposals: dict[int, ResearchProposal] = field(default_factory=dict)` (verified in `result.py:42`)

`len(result.proposals) > 0` works on a dict (returns number of keys), so the assertion is **syntactically correct** but the blueprint's prose implies a list. The test code must use `dict` semantics — i.e., the proposal synthesis stage must populate `result.proposals[key] = value`, not append to a list.

**Additionally:** The blueprint's "Best approach" suggests overriding `_init_core_services` to inject mocks. However, the `__init__` calls **19 `_init_*` methods** (verified: lines 141-159), and `_init_core_services` is only ONE of them. The other 18 (`_init_memory`, `_init_governance`, `_init_graph_rag`, `_init_session`, etc.) will also try to import and instantiate real services. The suggested approach of subclassing and overriding only `_init_core_services` is **insufficient** — the test will crash on imports of services like `SearchService()`, `KnowledgeGraph()`, `WorldModel()`, etc. before it even reaches `_build_stages()`.

**Required fix:** The DATA MODELS section must document the full mock surface — all 19 `_init_*` methods need either (a) override in a test subclass, or (b) `unittest.mock.patch` at the module level before `PipelineOrchestrator.__init__()` is called. Approach (b) is more robust and doesn't require subclassing.

---

## CHK-08: Authority Rules

**Result:** ✅ PASS

| AUTH | Description | Assessment |
|:-----|:------------|:-----------|
| AUTH-01 | Use `asyncio.run()` not `@pytest.mark.asyncio` | Correct. `run()` is `async def` (line 1021). `asyncio.run()` avoids trio-mode failures (GOTCHA-001). |
| AUTH-02 | Deterministic mocks | Standard best practice. |
| AUTH-03 | 60s timeout | Reasonable safeguard. |

---

## CHK-09: Dependencies

**Result:** ✅ PASS

BATCH-172, 173, 174 all CLOSED. No open dependencies. READ ONLY on orchestrator.py and stages.py is correctly scoped. No circular dependency risk.

---

## CHK-10: Task Completeness

**Result:** ✅ PASS

Two tasks cover the full scope:
- TASK-01: Mock infrastructure + full pipeline run (Critical)
- TASK-02: Stage ordering + regression + batch close (High)

TASK-02 correctly depends on TASK-01. No orphan work items.

---

## CHK-11: Task Coherence

**Result:** ✅ PASS

Tasks are cohesive — TASK-01 builds the infrastructure and primary assertions, TASK-02 adds ordering verification and batch hygiene. No cross-contamination between tasks. Both write to the same test file, which is correct for a cohesive integration test suite.

---

## CHK-12: Test Coverage / Sufficiency

**Result:** ✅ PASS

11 tests across 2 tasks:

| Task | Tests | Coverage |
|:-----|:------|:---------|
| TASK-01 | 7 tests (TEST-175-01-01 through 01-07) | Pipeline run, 16 stages, core stage status, papers, gaps, ideas, proposals |
| TASK-02 | 4 tests (TEST-175-02-01 through 02-04) | Stage order, regressions, STATE.md, CHANGELOG |

Each test has explicit failure mode and falsification strategy. TEST-175-01-02 (16 stages) directly validates HB-03. TEST-175-02-01 (ordering) validates BAC-03. Coverage is sufficient for the stated goal.

---

## CHK-13: Test Baseline

**Result:** ⚠️ **FINDING F-02 (Minor)**

| Claim | Source | Verified? |
|:------|:-------|:----------|
| Baseline: 2,815 tests | Blueprint TEST BASELINE | ⚠️ Inconsistent with STATE.md |
| STATE.md: "Last verified count: 2,769" | STATE.md TEST BASELINE | STATE.md was not updated after BATCH-174 |

STATE.md shows `2,769` as last verified count from BATCH-172, and BATCH-174 summary says `2,790 → 2,815 (+25)`. The blueprint's `2,815` is consistent with BATCH-174's delta but **STATE.md was not updated** after BATCH-174. This is a state hygiene issue.

**Expected delta:** +8 tests (7 from TASK-01 + 4 from TASK-02, but TEST-175-02-03 and 02-04 are unit/content checks, not pytest-counted tests — so actually 9 test functions, not 8). Blueprint claims `+8` but lists 11 test IDs. If TASK-02's STATE.md and CHANGELOG checks (02-03, 02-04) are simple assertions within a test function rather than separate `test_*` functions, the count may be correct, but this should be clarified.

---

## CHK-14: Task Dependencies

**Result:** ✅ PASS

TASK-01 → TASK-02 dependency is correctly declared and logically sound (must have mock infrastructure before testing ordering). Sequential execution is correct.

---

## CHK-15: Scope Coverage

**Result:** ✅ PASS

Every MUST-item in the scope maps to at least one test:
- Mock setup → TEST-175-01-01
- 16 stages → TEST-175-01-02
- Core stages "executed" → TEST-175-01-03
- papers_found > 0 → TEST-175-01-04
- gaps > 0 → TEST-175-01-05
- ideas > 0 → TEST-175-01-06
- proposals > 0 → TEST-175-01-07
- Stage order → TEST-175-02-01
- No regressions → TEST-175-02-02
- STATE.md → TEST-175-02-03
- CHANGELOG → TEST-175-02-04

---

## CHK-16: Consistency

**Result:** ⚠️ **FINDING F-03 (Minor)**

Two minor inconsistencies:

1. **Test count discrepancy:** Blueprint header says `+8 new tests`, but lists 11 TEST-IDs (7 + 4). If some are assertions within a single test function, this should be stated explicitly.

2. **"Core stages (0-4)" vs. "literature_search, ingestion, gap_analysis, idea_generation":** AC-01-03 says "Core stages (0-4) execute successfully" and lists indices 0-4 (which would be stages 0-4 in _STAGE_ORDER: literature_search, ingestion, gap_analysis, gap_reflection, idea_generation). But the scope says "at least literature_search, ingestion, gap_analysis, idea_generation have status executed" — which is only 4 stages (indices 0, 1, 2, 4), skipping index 3 (gap_reflection). The scope and AC are slightly misaligned.

---

## CHK-17: Lint Command

**Result:** ✅ PASS

```
python -m pytest backend/tests/test_pipeline/test_batch175_*.py -v --tb=short -p no:asyncio
```

Correct pattern. `-p no:asyncio` avoids GOTCHA-001 (trio-mode failures). Glob pattern `test_batch175_*` captures both TASK-01 and TASK-02 files (though both tasks are in a single file per DATA MODELS).

---

## CHK-18: Batch-Level Acceptance Criteria Completeness

**Result:** ✅ PASS

BAC-01 through BAC-06 cover: test execution, stage count, stage order, regression safety, documentation, and archiving. All are binary-pass criteria. No missing acceptance gates.

---

## INVESTIGATIVE CHECKS (CHK-19 through CHK-24)

### CHK-19: Data Model Verification

**Result:** ⚠️ **FINDING F-04 (Major)**

Verified against source code:

| Blueprint Claim | Source Truth | Match? |
|:----------------|:-------------|:-------|
| 16 stages in _STAGE_ORDER | 16 entries (lines 72-87) | ✅ |
| 16 stages in _build_stages return | 16 items (lines 1001-1016) | ✅ |
| `result.papers_found > 0` | `papers_found: int = 0` (result.py) | ✅ |
| `len(result.gaps) > 0` | `gaps: list[ResearchGap]` (result.py) | ✅ |
| `len(result.ideas) > 0` | `ideas: list[ResearchIdea]` (result.py) | ✅ |
| `len(result.proposals) > 0` | `proposals: dict[int, ResearchProposal]` (result.py) | ⚠️ **Type is dict, not list** |
| stage_report has 16 entries | `stage_report: list = field(default_factory=list)` (result.py) | ✅ |
| StageReport statuses | `"executed"`, `"skipped_by_strategy"`, etc. (orchestrator.py:1200-1240) | ✅ |

**`proposals` type issue (recap of F-01):** `proposals` is `dict[int, ResearchProposal]`. The assertion `len(result.proposals) > 0` works on a dict (counts keys), but the test must ensure the proposal synthesis mock populates the dict correctly — i.e., `result.proposals[idx] = ResearchProposal(...)` not `result.proposals.append(...)`. The blueprint should note this explicitly since the builder may assume list semantics.

---

### CHK-20: File Reality

**Result:** ✅ PASS

| Path | Exists? | Notes |
|:-----|:--------|:------|
| `backend/pipeline/orchestrator.py` | ✅ | 2173 lines, read in full |
| `backend/pipeline/stages.py` | ✅ | Contains all 16 stage classes |
| `backend/pipeline/result.py` | ✅ | PipelineResult + StageReport verified |
| `docs/aiv/STATE.md` | ✅ | Last updated BATCH-174 |
| `docs/aiv/BATCH-175/` | ✅ | Contains BLUEPRINT.md |
| `CHANGELOG.md` | ✅ | Exists, 36KB |
| `backend/tests/test_pipeline/test_batch174_*.py` | ✅ | 3 files (dependency reference) |

New file `backend/tests/test_pipeline/test_batch175_e2e_integration.py` does not yet exist — correct, this is what the batch creates.

---

### CHK-21: Feasibility

**Result:** ⚠️ **FINDING F-05 (Major)**

**Mock surface is far larger than documented.**

The blueprint suggests overriding `_init_core_services` to inject mocks. However, the `__init__` method calls **19 `_init_*` methods** in sequence (lines 141-159), each of which imports and instantiates real services:

| Method | Key Services Created |
|:-------|:---------------------|
| `_init_core_services` | SearchService, PDFService, EmbeddingService, VectorStore, BM25Index, TwoStageRetriever, GapAnalyzer, NoveltyChecker, FeasibilityScorer, ProposalSynthesizer, ExportService, AgentOrchestrator, DAGExecutor, MessageBus, KnowledgeGraph (indirectly) |
| `_init_memory` | MemoryService or TieredMemoryService, SharedKnowledgeBase |
| `_init_cross_stage_context` | CrossStageContext, LayeredPromptBuilder |
| `_init_self_improve` | PipelineEvolver, LessonExtractor, EvolutionEngine, ABTestHarness, SkillRegistry |
| `_init_autonomy` | SimpleBudget, HookDispatcher, ConsciousnessStateMachine, CuriosityDriver |
| `_init_governance` | OutputValidator, GovernanceAuditLog, GovernancePolicy, KnowledgeGraph, WorldModel, GoalManager |
| `_init_evaluation` | PipelineEvaluator, QualityGate, EvaluationCache |
| `_init_sandboxing` | SandboxManager |
| `_init_observability` | ObservabilityManager |
| `_init_metacognitive` | MetacognitiveManager |
| `_init_mcp` | MCPManager, MCPServerRegistry |
| `_init_context_management` | ContextWindowManager |
| `_init_streaming` | StreamManager |
| `_init_consolidation` | LLMConsolidator, ConsolidationScheduler |
| `_init_adaptation` | AdaptationManager |
| `_init_graph_rag` | GraphRAGRetriever, EntityExtractor, CommunityDetector |
| `_init_tool_discovery` | ToolMatcher, ToolScorer |
| `_init_negotiation` | ConsensusEngine |
| `_init_session` | SessionManager |

Plus the constructor itself creates: `StrategyRegistry`, `HookDispatcher`, `PipelinePersistence`, `TokenCounter`, `CompactionMiddleware`, `ReferenceVerifier`, and imports/registers builtin tools.

**The "Best approach" in DATA MODELS (subclass + override `_init_core_services`) will fail.** When `_init_memory` runs, it tries to create a `TieredMemoryService` which requires a real retriever. When `_init_governance` runs, it creates a `KnowledgeGraph` with a file path. When `_init_graph_rag` runs, it imports entity extraction modules. These will fail or create side effects.

**Recommended approach (must be added to blueprint):**

Use `unittest.mock.patch` at the module/class level for the key factories, OR override ALL `_init_*` methods in a test subclass to set `self._*` attributes to mocks without importing real services. The simplest pattern:

```python
class MockedOrchestrator(PipelineOrchestrator):
    """Test subclass that overrides all _init_* methods with no-ops."""
    
    def _init_core_services(self, settings):
        # Inject mock services directly
        self._search = MagicMock()
        self._embedding = MagicMock()
        ...
    
    def _init_memory(self, settings): pass
    def _init_cross_stage_context(self, settings): pass
    def _init_self_improve(self, settings): pass
    # ... override ALL 19 methods
```

But note: `_build_stages` still runs after the `_init_*` methods, so ALL services it references (`self._search`, `self._store`, `self._bm25`, `self._embedding`, `self._kg`, etc.) must be set as mocks in `_init_core_services` (or wherever they're first expected).

**Impact on execution SLA:** Building this mock surface may push TASK-01 beyond the 90-minute SLA. Consider splitting TASK-01 into TASK-01a (mock infrastructure) and TASK-01b (pipeline run test).

---

### CHK-22: Boundary Integrity

**Result:** ✅ PASS

Hard boundaries are enforced:
- HB-01 (real orchestrator): Test imports `PipelineOrchestrator` directly — no `Mock(spec=PipelineOrchestrator)`.
- HB-02 (no services): Mocks return deterministic values without network.
- HB-03 (fails on unwired stage): `len(result.stage_report) == 16` assertion will catch missing stages.

The blueprint correctly scopes READ ONLY on orchestrator.py and stages.py. The `skip_stages` parameter in `run()` could potentially be misused to skip stages, but the test doesn't use it, so this isn't a concern.

---

### CHK-23: Test Plan Adequacy

**Result:** ✅ PASS

Test plan is adequate for the stated goal. Each test has:
- Explicit behavior verified
- Failure mode documented
- Falsification strategy (how to make it fail)
- Pass criteria

The falsification strategies are particularly strong (e.g., "Unwire a stage" for TEST-175-01-01, "Remove stage from _build_stages" for TEST-175-01-02). These give the implementer clear guidance on what NOT to do.

---

### CHK-24: State Consistency

**Result:** ✅ PASS (with hygiene note)

| Check | Status |
|:------|:-------|
| STATE.md last updated | BATCH-174 (2026-05-11) — but test baseline NOT updated (still shows 2,769) |
| BATCH-174 marked complete in STATE.md | Yes — functional test suite section present |
| BATCH-175 section in STATE.md | Not yet — TASK-02 will add it |
| Dependency batches (172-174) all CLOSED | Yes |
| DEC-003 (stage names) matches _STAGE_ORDER | Yes — all 16 verified |
| DEC-004 (16 entries) matches source | Yes |

**Hygiene note:** STATE.md test baseline should be updated from 2,769 to 2,815 as part of TASK-02's scope (currently listed under BATCH-174 section but baseline not incremented). The blueprint's TEST BASELINE section correctly states 2,815, so the implementer has the right number.

---

## FINDINGS SUMMARY

### Major Findings (must fix before execution)

| ID | CHK | Severity | Summary |
|:---|:----|:---------|:--------|
| **F-01** | CHK-07, CHK-19 | Major | `proposals` is `dict[int, ResearchProposal]`, not a list. Blueprint should explicitly note dict semantics. Test must populate via key assignment, not append. |
| **F-05** | CHK-21 | Major | Mock surface is far larger than documented. 19 `_init_*` methods need override/patch, not just `_init_core_services`. The suggested "Best approach" (subclass + override `_init_core_services` only) will crash. Must document full mock surface or recommend `unittest.mock.patch` pattern. Consider splitting TASK-01 into 01a (mock infra) + 01b (pipeline run) to stay within 90-min SLA. |

### Minor Findings (recommend fix, non-blocking)

| ID | CHK | Severity | Summary |
|:---|:----|:---------|:--------|
| **F-02** | CHK-13 | Minor | STATE.md test baseline not updated after BATCH-174 (still shows 2,769, should be 2,815). TASK-02 should fix this. |
| **F-03** | CHK-16 | Minor | Test count discrepancy: header says +8 but lists 11 TEST-IDs. Also AC-01-03 "Core stages (0-4)" vs scope "literature_search, ingestion, gap_analysis, idea_generation" (indices 0,1,2,4 — missing gap_reflection at index 3). |
| **F-04** | CHK-19 | Minor | Blueprint DATA MODELS section lists mock targets from `_init_core_services` only, missing services from the other 18 `_init_*` methods. At minimum, note that all `_init_*` methods must be handled. |

---

## VERDICT

**CONDITIONAL PASS**

The blueprint is well-structured, goal-oriented, and has strong test plan adequacy. The two **major findings** (F-01 proposals type, F-05 mock surface) are execution-critical and must be resolved before the lead begins TASK-01, otherwise the task will fail during implementation and require rework.

**Recommended lead actions:**
1. Update DATA MODELS section with full mock surface (all 19 `_init_*` methods)
2. Note `proposals` is a dict — update TEST-175-01-07 pass criteria accordingly
3. Clarify test count (+8 vs 11 TEST-IDs)
4. Consider TASK-01 split if mock surface work threatens 90-min SLA
5. Update STATE.md baseline as part of TASK-02

---

*End of Review Report. Awaiting Lead Response.*
