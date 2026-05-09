# BATCH-137 BLUEPRINT REVIEW REPORT

**Reviewer:** Craft Agent (AIV Framework v5.3 — Advisory Role)
**Date:** 2026-05-10
**Blueprint Version:** 1.0
**Cycle Mode:** STANDARD

---

## STRUCTURAL LAYER (CHK-00 – CHK-18)

### CHK-00 — CYCLE MODE
**PASS.** STANDARD mode with 3 Tasks (T1, T2, T3), all modifying existing files. Consistent.

### CHK-01 — BATCH ID
**PASS.** BATCH-137 is present, correctly formatted.

### CHK-02 — SLA FIELDS
**PASS.** Review SLA: 30 min, Execution SLA per Task: 90 min, Partial Sign-Off SLA: 15 min — all numeric, all present.

### CHK-03 — BATCH GOAL
**PASS.** Single, clear, deployable outcome: remove secrets from git history, add startup guards, ensure .env.example is the sole template.

### CHK-04 — SCOPE COMPLETENESS
**PASS.** MUST section covers git untracking, .gitignore enforcement, .env.example update, startup checks, and IP removal. MUST NOT section covers no pipeline logic changes, no runtime behavior changes, no field removal, no new dependencies.

### CHK-05 — BATCH ACCEPTANCE
**PASS.** BAC-01 through BAC-04 cover the full Batch Goal: git tracking, credentials, changelog, and archival.

### CHK-06 — HARD BOUNDARIES
**PASS.** HB-01 (git ls-files returns empty), HB-02 (grep for hex strings), HB-03 (app starts with placeholders only) — all are falsifiable with concrete commands.

### CHK-07 — DATA MODELS
**PASS.** Explicitly states "No data model changes." References specific existing modules with field names, types, and source locations. Sufficient for implementation.

### CHK-08 — AUTHORITY RULES
**PASS.** AUTH-01 (.env sole source of secrets), AUTH-02 (startup() sole place for warnings), AUTH-03 (warnings non-blocking). No HB contradictions — AUTH-03 aligns with HB-03.

### CHK-09 — DEPENDENCY MAP
**PASS.** Declared "No prior Batch dependencies. Standalone hardening Batch." — consistent with the scope.

### CHK-10 — TASK COMPLETENESS
**PASS.** All three Tasks have descriptions, files in scope, tests, and acceptance criteria with traceability.

### CHK-11 — TASK COHERENCE
**PASS.** T1 = git untracking + .env.example. T2 = startup warnings. T3 = hardcoded IP removal. Each is one concern.

### CHK-12 — TEST COVERAGE
**PASS.** All 11 tests have IDs (TEST-137-XX-XX), types (all unit), behaviors, failure modes, falsification methods, and pass criteria.

### CHK-13 — TEST SUFFICIENCY
**FLAG.** TEST-137-02-03 ("Startup warns when no LLM API key configured") and TEST-137-02-04 cover the LM Studio path, but no test verifies the behavior when `lmstudio_enabled=True AND no LLM API key AND` the LM Studio base URL is unreachable — the Blueprint claims a warning should NOT fire in this case, but there is no negative test for the "LM Studio enabled but server down" scenario where the app still starts. Boundary condition is partially covered but the edge case of LM Studio enabled + unreachable is not tested.

### CHK-14 — TEST BASELINE
**FLAG.** Blueprint claims baseline of 2,416 collected tests. STATE.md last verified count is 2,292 (BATCH-120), with Phase 9 summary showing total test baseline of 2,361. The Blueprint's 2,416 figure is 55 tests above STATE.md's 2,361 with no documented BATCH (B130–B136) delta explaining the gap. STATE.md was last updated 2026-05-07 and claims B121–B129 were the latest batches recorded, but the Blueprint asserts B121–B136 have run since that update (16 batches). The baseline is not grounded in STATE.md.

### CHK-15 — TASK DEPENDENCIES
**PASS.** T2 depends on T1; T3 depends on T2. Sequential, non-circular.

### CHK-16 — SCOPE COVERAGE
**PASS.** T1 covers git/.gitignore/.env.example. T2 covers startup warnings. T3 covers hardcoded IPs. Together they cover all MUST items.

### CHK-17 — INTERNAL CONSISTENCY
**FLAG.** AUTH-03 states "The application must never refuse to start — only warn loudly," but the Batch Goal says "add startup guards that refuse to run with insecure defaults." The word "refuse" in the Batch Goal contradicts AUTH-03's "never refuse to start." Either the Batch Goal wording is imprecise or AUTH-03 is wrong.

### CHK-18 — LINT COMMAND
**PASS.** Present and non-empty: `python -m ruff check backend/api/ backend/providers/ backend/config.py && npx tsc --noEmit --project frontend/tsconfig.json`

---

## INVESTIGATIVE LAYER (CHK-19 – CHK-24)

### CHK-19 — DATA MODEL VERIFICATION
**FLAG.** Three stale references found:
1. **provider_factory.py line 306:** Blueprint claims `base_url=getattr(settings, "ollama_base_url", "http://localhost:11434")` at line 306. Actual line 306 is inside the `_wrap_cached()` function for embedding cache setup — the `ollama_base_url` getattr there is for embedding configuration, not the provider construction the Blueprint's DATA MODELS section implies. The provider construction `ollama` path is at line 159 (`base_url=settings.ollama_base_url`) with no hardcoded fallback.
2. **app.py startup() location:** Blueprint claims `line ~245`. Actual location is line 234-235 (`@app.on_event("startup")` / `async def startup()`). Minor but imprecise for a verified reference.
3. **.env.example field count:** Blueprint claims "23 fields — currently 23 fields." Actual `.env.example` contains only 12 `EROCK_` prefixed fields (924 bytes confirmed). The Blueprint's DATA MODELS section and SCOPE both claim 23 fields, but the file has only 12. The Blueprint's T1 scope says to "expand" it, but the claimed current count is wrong.

### CHK-20 — FILE REALITY CHECK
**PASS.** All declared files verified to exist: config.py, app.py, provider_factory.py, embedding_providers.py, ollama_provider.py, pdf_service.py, otlp_exporter.py, manager.py, orchestrator.py, .env.example, .gitignore. Test file paths (new) are in an existing directory (backend/tests/test_pipeline/). No conflicts.

### CHK-21 — SCOPE FEASIBILITY
**PASS.** T1 (git untrack + .env.example update) is straightforward. T2 (2 startup warnings) is small-scope. T3 (IP replacement across ~7 files) is mechanical. Sequential execution within 90 min/task is achievable.

### CHK-22 — TASK BOUNDARY INTEGRITY
**FLAG.** T3 declares `backend/config.py` as a file in scope (changing `lmstudio_base_url` default), but T1's acceptance criteria AC-01-03 requires `.env.example` to document `lmstudio_base_url`. The config.py default value change in T3 directly affects the meaning of the `.env.example` field documented in T1. This coupling is undocumented — T1 runs before T3, so T1's .env.example documentation of `lmstudio_base_url` may describe a default value that T3 will later change.

### CHK-23 — TEST PLAN ADEQUACY
**FLAG.** TEST-137-03-01 greps for "non-localhost IP patterns in backend/pipeline/ and backend/providers/" but the grep pattern is not precisely defined. The pass criteria says "grep for non-localhost IP patterns" returns 0 matches, but does not specify the regex. Different regex patterns (e.g., `\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}` vs. `100\.64` vs. `192\.168`) would yield different results. The test is insufficiently specified to be reliably falsifiable.

### CHK-24 — STATE CONSISTENCY
**FLAG.** Three inconsistencies with STATE.md:
1. **Test baseline:** Blueprint claims 2,416; STATE.md documents 2,361 (Phase 9 close) with last verified count of 2,292. The 55-test gap (B130–B136) is undocumented in STATE.md.
2. **STATE.md staleness:** STATE.md was last updated 2026-05-07 by BATCH-120. The Blueprint claims B121–B136 have since run (16 batches). STATE.md contains Phase 9 module entries (B121–B129) but was not formally updated with a new "Last Updated" timestamp reflecting B129+ closure.
3. **Module map scope:** STATE.md does not mention security, configuration, or environment-variable management modules — consistent with this being a new concern, but the Blueprint's reconciliation audit claims "all Phase 9 module entries verified present" while STATE.md hasn't been updated since B120.

---

## SUMMARY

| Category | Count |
|----------|-------|
| Total Checks | 25 |
| PASS | 18 |
| FLAG | 7 |

### Flags by Severity

| ID | Severity | Issue |
|----|----------|-------|
| CHK-17 | **HIGH** | Batch Goal says "refuse to run" — contradicts AUTH-03 ("never refuse to start") and HB-03 ("startup warnings acceptable; crashes are not") |
| CHK-19 | **HIGH** | .env.example has 12 EROCK_ fields, not 23 as claimed; provider_factory.py line 306 reference is wrong context; app.py startup() line number off by ~11 lines |
| CHK-24 | **HIGH** | Test baseline 2,416 is unsupported — STATE.md documents 2,361; 16 batches (B121–B136) have run since STATE.md was last updated |
| CHK-14 | **MEDIUM** | Test baseline figure 2,416 is not grounded in STATE.md — no delta documentation for B130–B136 |
| CHK-22 | **MEDIUM** | Undocumented coupling: T3 changes the config.py default that T1's .env.example documentation references |
| CHK-13 | **LOW** | Missing edge-case test: LM Studio enabled + server unreachable |
| CHK-23 | **LOW** | TEST-137-03-01 grep pattern for non-localhost IPs is not precisely specified |

---

## RECOMMENDATION

**REVISE BEFORE EXECUTION.** Three HIGH-severity flags require Lead action:

1. **Resolve the "refuse" vs. "warn" contradiction** (CHK-17) — the Batch Goal, AUTH-03, and HB-03 must use consistent language. Recommend the Batch Goal be amended to say "warn when insecure defaults are detected" to align with AUTH-03.
2. **Correct .env.example field count** (CHK-19) — the actual count is 12, not 23. T1's scope should reflect the real current state and describe the expansion delta.
3. **Ground the test baseline** (CHK-24) — either update STATE.md to document B130–B136 deltas, or re-derive the baseline from a live `pytest --collect-only` count.

The Lead may proceed at their discretion after addressing these items.

---

*End of Review Report.*
