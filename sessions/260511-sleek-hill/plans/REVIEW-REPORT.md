# REVIEW REPORT — BATCH-174

**Reviewer:** Craft Agent (Blueprint Reviewer, AIV v5.3)
**Date:** 2026-05-11T17:53 UTC+3
**Blueprint Version:** 1.0
**Cycle Mode:** STANDARD
**Verdict:** **REJECT — 1 Fatal, 6 Advisory**

**Intended location:** `docs/aiv/BATCH-174/REVIEW-REPORT.md`

---

## CHECKLIST RESULTS

### CHK-00 CYCLE MODE — FLAG ⚠
TASK-03 files in scope include `docs/aiv/STATE.md` and `CHANGELOG.md`, which are not test files. The Cycle Mode header and Scope suggest a test-only batch, but TASK-03 performs documentation mutations outside the test file boundary.

### CHK-01 BATCH ID — PASS
`BATCH-174`, formatted as `BATCH-NN`.

### CHK-02 SLA FIELDS — PASS
Review SLA: 30 min (numeric). Execution SLA per Task: 90 min (numeric). Partial Sign-Off SLA: 15 min (numeric).

### CHK-03 BATCH GOAL — PASS
Single clear deployable outcome: functional tests for all 16 pipeline stages with execute() verification.

### CHK-04 SCOPE — PASS
Four MUST items (write functional tests, use mock LLM, independently runnable, distinguish real execution from import-level mocking) and four MUST NOT items.

### CHK-05 BATCH ACCEPTANCE — PASS
BAC-01 through BAC-05 cover the full Goal: 16+ tests, no source changes, no regressions, CHANGELOG updated, documents archived.

### CHK-06 HARD BOUNDARIES — PASS
All three HBs are falsifiable (HB-01: grep for execute() calls; HB-02: assert mutation not just return; HB-03: diff against backend/pipeline/).

### CHK-07 DATA MODELS — FLAG ⚠
Constructor args in the data model table are oversimplified and do not match actual stage signatures (see CHK-19 for full detail). Module paths for test files are correct, but the constructor column will mislead implementers into creating wrong mock objects.

### CHK-08 AUTHORITY RULES — PASS
AUTH-01 through AUTH-03 present. AUTH-02 provides a fallback for complex deps without contradicting HBs (it requires documentation, not silence). AUTH-01 reserves waiving authority to Lead.

### CHK-09 DEPENDENCY MAP — PASS
BATCH-172 (CLOSED), BATCH-173 (CLOSED), `stages.py` (READ ONLY), `result.py` (READ ONLY). No unresolved dependencies.

### CHK-10 TASK COMPLETENESS — PASS
Every Task has description, files in scope, test IDs, and acceptance criteria with traceability.

### CHK-11 TASK COHERENCE — PASS
TASK-01: core stages (0–8). TASK-02: synthesis stages (9–15). TASK-03: verification and batch close. One concern per task.

### CHK-12 TEST COVERAGE — PASS
All 20 tests have ID, type, behavior verified, failure mode, falsified-by, and pass criteria columns populated.

### CHK-13 TEST SUFFICIENCY — FLAG ⚠
No error-path tests (e.g., provider raises exception, empty input lists, malformed LLM response). No boundary-condition tests. AUTH-03 requires True/False return-path testing for early-exit stages, but no test covers a False return path.

### CHK-14 TEST BASELINE — PASS
Baseline 2,790 matches BATCH-173 close (2,769 + 21). Expected delta +20, total 2,810.

### CHK-15 TASK DEPENDENCIES — PASS
TASK-01 → none. TASK-02 → TASK-01 (pattern only). TASK-03 → TASK-01 + TASK-02. Sequential, non-circular.

### CHK-16 SCOPE COVERAGE — PASS
TASK-01 covers stages 0–8 (9 stages). TASK-02 covers stages 9–15 (7 stages). 9 + 7 = 16 stages = full scope.

### CHK-17 INTERNAL CONSISTENCY — FLAG ⚠
AUTH-03 mandates testing both True and False return paths for early-exit stages, but zero tests in any task table cover a False-return scenario. The Blueprint internally contradicts its own Authority Rule.

### CHK-18 LINT COMMAND — PASS
Present and non-empty: `python -m pytest backend/tests/test_pipeline/test_batch174_*.py -v --tb=short -p no:asyncio`.

---

## INVESTIGATIVE LAYER

### CHK-19 DATA MODEL VERIFICATION — FATAL ☠

**Constructor args vs actual code — 10 of 16 stages have material mismatches:**

| # | Blueprint Claims | Actual `__init__` Signature | Verdict |
|:--|:-----------------|:----------------------------|:--------|
| 0 | search_service, hooks | `(search, hooks)` | MATCH (param name minor) |
| 1 | embedding_service, summarizer | `(store, bm25, embedding, kg=None, provider=None)` | **MISMATCH** — completely different shape |
| 2 | provider, cluster_service, deduplicator | `(gap_analyzer, goal_manager, hooks, memory, kg=None, faithfulness_checker=None)` | **MISMATCH** — wrong types, missing deps |
| 3 | provider | `(provider=None, reflector=None, threshold=0.6)` | PARTIAL — has extra args |
| 4 | ideator | `(agent, hooks, dag_executor=None, dag_agents=None, provider=None, kg=None, forest=None, reasoning_verifier=None)` | **MISMATCH** — wrong name, many extra deps |
| 5 | provider | `(provider=None, reflector=None, threshold=0.6)` | PARTIAL |
| 6 | novelty_checker, s2_verifier | `(novelty_checker, hooks=None)` | **MISMATCH** — no s2_verifier parameter |
| 7 | provider | `(feasibility_scorer)` | **MISMATCH** — takes scorer object, not provider |
| 8 | (none) | `(self)` | MATCH |
| 9 | provider | `(synthesizer, governance_validator=None, governance_audit=None, ref_validator=None)` | **MISMATCH** — takes synthesizer, not provider |
| 10 | provider | `(reviewer, synthesizer, generation_provider=None, thinking_provider=None)` | **MISMATCH** — takes reviewer + synthesizer |
| 11 | provider | `(provider=None, evaluator=None)` | PARTIAL — has evaluator too |
| 12 | provider | `(provider=None, synthesizer=None)` | PARTIAL |
| 13 | provider | `(provider=None, auditor=None)` | PARTIAL |
| 14 | provider | `(deepener=None)` | **MISMATCH** — takes deepener, not provider |
| 15 | (config) | `(export_service)` | **MISMATCH** — takes export_service, not config |

**"Must Mutate" vs actual execute() behavior — 6 of 16 stages target wrong fields:**

| # | Blueprint Claims Mutated | What execute() Actually Mutates | Verdict |
|:--|:-------------------------|:--------------------------------|:--------|
| 1 | `ctx.result.papers_found` | Adds papers to store/BM25/KG — does NOT set papers_found (that is stage 0) | **MISMATCH** |
| 3 | `ctx.result.gaps` modified | `ctx.result.reflection_results["gap_reflection"]` (dynamically created attr) — gaps unchanged | **MISMATCH** |
| 5 | `ctx.result.ideas` modified | `ctx.result.reflection_results["idea_reflection"]` — ideas unchanged | **MISMATCH** |
| 10 | `ctx.result.critique_history` | Writes to proposal metadata via `_set_metadata()` — critique_history NOT populated | **MISMATCH** |
| 11 | `ctx.result.evaluation_reports` | Writes to proposal metadata — evaluation_reports dict NOT populated | **MISMATCH** |
| 13 | `ctx.result.quality_report` or proposal metadata | Writes to proposal metadata only — quality_report NOT set | **MISMATCH** |

**Impact:** Test pass criteria (e.g., `len(ctx.result.critique_history) > 0` for stage 10) will produce false negatives. An implementer following the Blueprint table will write tests that cannot pass against the actual code.

### CHK-20 FILE REALITY CHECK — PASS

- Source files `stages.py` and `result.py` exist and are readable.
- Target test files (`test_batch174_*.py`) are new — correctly not expected to exist yet.
- `CHANGELOG.md` and `docs/aiv/STATE.md` exist.
- Existing `conftest.py` fixtures (`SchemaAwareFakeProvider`, `sample_proposal`, etc.) are usable as-is.

### CHK-21 SCOPE FEASIBILITY — PASS

- TASK-01: 9 tests in 90 min ≈ 10 min/test. Feasible.
- TASK-02: 7 tests in 90 min ≈ 13 min/test. Feasible given pattern reuse from TASK-01.
- TASK-03: 4 tests + 2 doc updates in 90 min. Feasible.

### CHK-22 TASK BOUNDARY INTEGRITY — PASS

TASK-01 and TASK-02 are in separate files with no shared mutable state. TASK-02 declares a pattern dependency on TASK-01 (not a state dependency). TASK-03 is an integration reader, not a mutator of TASK-01/TASK-02 state.

### CHK-23 TEST PLAN ADEQUACY — FLAG ⚠

- **TASK-01 falsifiable?** Pass criteria are individually falsifiable (e.g., `len(ctx.result.gaps) > 0`), BUT they target wrong mutation fields per CHK-19, so tests will fail against real code.
- **TASK-02 error paths?** None. Seven tests cover only the happy path. AUTH-03's True/False requirement is unaddressed.
- **Critical priority coverage?** TASK-01 and TASK-02 are both Critical but have zero boundary-condition or failure-mode tests despite stages having multiple early-exit branches and exception handlers.

### CHK-24 STATE CONSISTENCY — FLAG ⚠

STATE.md `TEST BASELINE` section says "Last verified count: 2,769" (verified in BATCH-172), while the BATCH-173 section records "Total test baseline: 2,769 → 2,790 (+21)". The main TEST BASELINE section was not reconciled after BATCH-173. The Blueprint correctly uses 2,790, but STATE.md itself is internally inconsistent.

---

## SUMMARY

| Category | Count |
|:---------|:------|
| Total checks | 25 |
| PASS | 18 |
| FLAG (Advisory) | 6 |
| FLAG (Fatal) | 1 |

---

## FATAL FLAGS

| ID | Check | Issue |
|:---|:-------|:------|
| F-01 | CHK-19 | Data model table is factually incorrect: 10/16 constructor signatures are wrong and 6/16 "Must Mutate" targets are wrong. Tests written from this table will not pass against the actual codebase. |

---

## ADVISORY FLAGS

| ID | Check | Issue |
|:---|:-------|:------|
| A-01 | CHK-00 | TASK-03 modifies non-test files (STATE.md, CHANGELOG.md), slightly beyond "only creates test files" framing. |
| A-02 | CHK-07 | Constructor column in data model table is oversimplified — will mislead implementers even if not blocking. |
| A-03 | CHK-13 | Zero error-path or boundary-condition tests across all tasks. |
| A-04 | CHK-17 | AUTH-03 mandates True/False path testing but no test in any task table covers a False return. Internal contradiction. |
| A-05 | CHK-23 | Critical-priority tasks lack failure-mode coverage despite stages having early-exit branches and exception handlers. |
| A-06 | CHK-24 | STATE.md TEST BASELINE section is stale (2,769) while BATCH-173 section shows 2,790. Needs reconciliation. |

---

## RECOMMENDATION

**REJECT — Blueprint requires revision before execution.**

The Blueprint must correct the data model table (F-01) before any task can proceed. Specifically:

1. **Rewrite the constructor column** to match actual `__init__` signatures from `stages.py`. The oversimplified "provider" shorthand is incorrect for stages that take specific service objects (gap_analyzer, agent, synthesizer, reviewer, feasibility_scorer, deepener, export_service, etc.).
2. **Correct the "Must Mutate" column** for stages 1, 3, 5, 10, 11, and 13 to reflect actual `execute()` behavior. Notably: GapReflectionStage and IdeaReflectionStage write to `reflection_results` (not gaps/ideas), AdversarialReviewStage writes to proposal metadata (not critique_history), and EvaluationStage writes to proposal metadata (not evaluation_reports).
3. **Resolve the AUTH-03 gap** by either adding False-return tests for early-exit stages or explicitly documenting the waiver.
4. **Reconcile STATE.md** TEST BASELINE section to 2,790 before batch execution.

Advisory flags (A-01 through A-06) should be addressed but are not blocking.
