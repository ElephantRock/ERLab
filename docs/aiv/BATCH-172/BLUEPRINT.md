# BATCH BLUEPRINT — BATCH-172

Batch ID:                 BATCH-172
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-11
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Mixed (TASK-01 first; TASK-02, TASK-03 parallel after; TASK-04 last)

---

## BATCH GOAL

Wire the 3 dead-coded pipeline stages (GapReflectionStage, IdeaReflectionStage, EvaluationStage) into the orchestrator's `_build_stages()` method and add a preflight check system that validates provider reachability before the API accepts a pipeline run. After this Batch, the API MUST NOT return `{"status":"running"}` unless the orchestrator can actually initialize and the database can persist a run record.

---

## SCOPE STATEMENT

**What the code MUST do:**
- Add GapReflectionStage, IdeaReflectionStage, EvaluationStage to the return list of `PipelineOrchestrator._build_stages()` at their correct positions in `_STAGE_ORDER` (indices 3, 5, 11)
- Each wired stage MUST use the correct provider (thinking_provider for reflection/evaluation)
- The preflight module (`backend/pipeline/preflight.py` — already exists) MUST be called by `trigger_run()` BEFORE returning "running"
- If any preflight check returns FATAL severity, the API MUST return HTTP 503 with a structured error body listing all failures
- If all checks pass or are WARNING-only, the API returns 202 as before but the response body now includes a "preflight" key with the report
- The preflight check MUST verify: LLM provider reachable, embedding provider reachable (non-fatal), database writable, strategy registered, domain non-empty, export dir writable

**What the code MUST NOT do:**
- MUST NOT change the behavior of any currently-working stage
- MUST NOT add new pipeline stages beyond the 3 that already exist
- MUST NOT remove or reorder any existing stage in `_build_stages()`
- MUST NOT make preflight checks blocking for WARNING severity (only FATAL blocks)
- MUST NOT introduce new dependencies beyond what's already imported

---

## LINT COMMAND

```
python -m pytest backend/tests/ -x -q --tb=line -p no:asyncio 2>&1 | tail -5
```

---

## HARD BOUNDARIES

- **HB-01**: The `_build_stages()` return list MUST contain exactly 16 PipelineStage instances matching the names in `_STAGE_ORDER`. Count verified by test: `len(stages) == 16` and `[s.name for s in stages] == _STAGE_ORDER`.
- **HB-02**: The API endpoint `POST /api/v1/pipeline/run` MUST NOT return HTTP 202 with `{"status":"running"}` if any preflight check reports FATAL severity. It MUST return HTTP 503 instead.
- **HB-03**: No existing stage may change its position. First 3 must remain: `literature_search`, `ingestion`, `gap_analysis`. Last must remain: `export`.
- **HB-04**: The preflight check MUST complete in under 30 seconds total. Each provider check has timeout: 15s (LLM), 10s (embedding), 5s (database/dir). Timeout = WARNING, not FATAL.

---

## DATA MODELS / SCHEMA

**Module: `backend.pipeline.orchestrator.PipelineOrchestrator`**
- `_STAGE_ORDER: list[str]` — 16 entries
- `_build_stages() -> list[PipelineStage]` — currently returns 13 stages
- `self._provider: LLMProvider` (cloud glm-5.1 via z.ai)
- `self._thinking_provider: LLMProvider | None` (local qwen3-4b via LM Studio)

**Module: `backend.pipeline.stages`**
- `GapReflectionStage(provider, reflector, threshold=0.6)` → `name = "gap_reflection"`
- `IdeaReflectionStage(provider, reflector, threshold=0.6)` → `name = "idea_reflection"`
- `EvaluationStage(provider, evaluator)` → `name = "evaluation"`

**Module: `backend.pipeline.reflection.reflector`**
- `ReflectionStage(provider, threshold=0.6, max_iterations=3)`

**Module: `backend.pipeline.evaluation.proposal_evaluator`**
- `ProposalEvaluator(provider)`

**Module: `backend.pipeline.preflight` (ALREADY EXISTS)**
- `run_preflight(domain, strategy, settings) -> PreflightReport`
- `PreflightReport(checks, can_proceed, warnings, errors, fatal)`
- `PreflightResult(name, severity, message, detail, latency_ms)`
- `CheckSeverity: OK | WARNING | ERROR | FATAL`

**Module: `backend.api.routes.pipeline`**
- `trigger_run(request: PipelineRunRequest)` — currently returns 200 immediately

---

## AUTHORITY RULES

- **AUTH-01**: Only the Lead may modify `_STAGE_ORDER`
- **AUTH-02**: Preflight FATAL is the sole gate for rejecting a run. WARNING must not block
- **AUTH-03**: thinking_provider preferred for reflection/evaluation. If unavailable, generation provider is fallback — WARNING logged
- **AUTH-04**: Strategy stage gating (existing behavior) remains unchanged

---

## DEPENDENCY MAP

- `backend.pipeline.stages` (3 stage classes — exist, unmodified)
- `backend.pipeline.reflection.reflector.ReflectionStage` (exists)
- `backend.pipeline.evaluation.proposal_evaluator.ProposalEvaluator` (exists)
- `backend.pipeline.preflight` (exists from prior session)
- `backend.api.routes.pipeline.trigger_run` (exists, needs modification)
- No external dependencies. No new packages.

---

## STATE.md STATUS

- State file exists: YES
- Last Updated: 2026-05-11 (BATCH-171)
- Batches since update: 0
- Reconciliation audit: N/A (< 5 batches)

---

## TEST BASELINE

- Baseline at Blueprint issuance: **2,743** existing tests
- Expected delta (all Tasks): **+24** new tests
- Expected total at Batch close: **2,767**

---

## TASK LIST

### TASK-01: BATCH-172/TASK-01 — Wire 3 Dead Stages into Orchestrator
- **Priority:** Critical
- **Description:** Add GapReflectionStage (position 3), IdeaReflectionStage (position 5), and EvaluationStage (position 11) to `_build_stages()`. Each uses thinking_provider (fallback: self._provider). Create ReflectionStage and ProposalEvaluator instances.
- **Files in scope:** `backend/pipeline/orchestrator.py` (lines ~990-1013, `_build_stages` method)
- **Depends on:** None

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-172-01-01 | unit | _build_stages returns 16 stages | Count mismatch | Remove one stage | `len(stages) == 16` |
| TEST-172-01-02 | unit | Names match _STAGE_ORDER | Wrong order | Swap two positions | `[s.name for s in stages] == _STAGE_ORDER` |
| TEST-172-01-03 | unit | gap_reflection at index 3 | Never executes | Comment out | `stages[3].name == "gap_reflection"` |
| TEST-172-01-04 | unit | idea_reflection at index 5 | Never executes | Comment out | `stages[5].name == "idea_reflection"` |
| TEST-172-01-05 | unit | evaluation at index 11 | Never executes | Comment out | `stages[11].name == "evaluation"` |
| TEST-172-01-06 | unit | Reflection uses thinking_provider | Wrong provider | Change to self._provider | `stage._provider is thinking_provider` or fallback exists |
| TEST-172-01-07 | integration | Orchestrator init succeeds | Missing arg crashes | Remove constructor param | `PipelineOrchestrator()` no exception |

**Acceptance Criteria:**
- AC-01-01: _build_stages() returns 16 stages matching _STAGE_ORDER
- AC-01-02: Stages at correct indices (3, 5, 11)
- AC-01-03: Stages receive thinking_provider when available
- AC-01-04: Orchestrator.__init__() succeeds with all 16 stages

**Traceability:** AC-01-01→T-01,T-02 | AC-01-02→T-03,T-04,T-05 | AC-01-03→T-06 | AC-01-04→T-07

---

### TASK-02: BATCH-172/TASK-02 — Wire Preflight into API Endpoint
- **Priority:** Critical
- **Description:** Modify `trigger_run()` to call `run_preflight()` BEFORE the background task. FATAL→503 with error body. OK/WARNING→202 with preflight key.
- **Files in scope:** `backend/api/routes/pipeline.py` (trigger_run function)
- **Depends on:** None (parallel with TASK-01)

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-172-02-01 | unit | Preflight importable | Import error | Add syntax error | `import run_preflight` succeeds |
| TEST-172-02-02 | integration | API returns 503 on FATAL LLM | False "running" | Mock FATAL | `status_code == 503` |
| TEST-172-02-03 | integration | API returns 503 on FATAL DB | False "running" | Mock DB exception | `status_code == 503` |
| TEST-172-02-04 | integration | API returns 202 with preflight on success | Blocks healthy run | All checks pass | `status_code == 202`, `"preflight" in body` |
| TEST-172-02-05 | integration | API returns 202 on embedding WARNING | Unnecessary block | Mock timeout | `status_code == 202` |
| TEST-172-02-06 | unit | PreflightReport structure correct | Missing fields | Remove field | Has .checks, .can_proceed, .warnings, .errors, .fatal |
| TEST-172-02-07 | integration | 503 body lists failures | Can't diagnose | Mock 2 FATALs | `len(fatal_checks) >= 2` |

**Acceptance Criteria:**
- AC-02-01: 503 on any FATAL check
- AC-02-02: 202 with preflight key on pass/WARNING
- AC-02-03: Embedding failure = WARNING (not FATAL)
- AC-02-04: 503 body has diagnostic detail

**Traceability:** AC-02-01→T-02,T-03 | AC-02-02→T-04,T-05 | AC-02-03→T-05 | AC-02-04→T-07

---

### TASK-03: BATCH-172/TASK-03 — Strategy Preset Validation
- **Priority:** High
- **Description:** Verify all 4 strategies correctly enable/disable the 3 new stages. deep_research/academic_proposal MUST enable them. fast_scan/literature_review MUST disable them. Update presets.py if needed.
- **Files in scope:** `backend/pipeline/strategies/presets.py`
- **Depends on:** None (parallel)

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-172-03-01 | unit | deep_research enables gap_reflection | Skipped on deep | Set enabled=False | `stages["gap_reflection"].enabled is True` |
| TEST-172-03-02 | unit | deep_research enables idea_reflection | Skipped on deep | Set enabled=False | `stages["idea_reflection"].enabled is True` |
| TEST-172-03-03 | unit | deep_research enables evaluation | Skipped on deep | Set enabled=False | `stages["evaluation"].enabled is True` |
| TEST-172-03-04 | unit | fast_scan disables all 3 | Runs expensive stages | Set enabled=True | All 3 `enabled is False` |
| TEST-172-03-05 | unit | literature_review disables all 3 | Runs unnecessary | Set enabled=True | All 3 `enabled is False` |

**Acceptance Criteria:**
- AC-03-01: deep_research enables gap_reflection, idea_reflection, evaluation
- AC-03-02: fast_scan disables all 3
- AC-03-03: literature_review disables all 3
- AC-03-04: academic_proposal enables all 3

**Traceability:** AC-03-01→T-01,T-02,T-03 | AC-03-02→T-04 | AC-03-03→T-05

---

### TASK-04: BATCH-172/TASK-04 — Verification and Batch Close
- **Priority:** Medium
- **Description:** Run full test suite. Verify no regressions. Verify _STAGE_ORDER matches _build_stages. Verify preflight integration. Update STATE.md and CHANGELOG.
- **Files in scope:** `docs/aiv/STATE.md`, `CHANGELOG.md`
- **Depends on:** TASK-01, TASK-02, TASK-03

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-172-04-01 | integration | Full suite passes | New code broke tests | Revert wiring | exit code 0, count == 2,767 |
| TEST-172-04-02 | integration | _STAGE_ORDER matches _build_stages | Declared ≠ built | Add extra name | names match |
| TEST-172-04-03 | integration | Preflight + trigger integration | Not called/ignored | Remove import | 503 on FATAL, 202 on OK |
| TEST-172-04-04 | unit | STATE.md has BATCH-172 | Stale state | Check content | `"BATCH-172" in STATE.md` |
| TEST-172-04-05 | unit | CHANGELOG has BATCH-172 | Missing trail | Check content | `"BATCH-172" in CHANGELOG` |

**Acceptance Criteria:**
- AC-04-01: All 2,767 tests pass
- AC-04-02: _STAGE_ORDER matches _build_stages()
- AC-04-03: STATE.md + CHANGELOG updated

**Traceability:** AC-04-01→T-01 | AC-04-02→T-02 | AC-04-03→T-04,T-05

---

## BATCH-LEVEL ACCEPTANCE CRITERIA

- **BAC-01**: `_build_stages()` returns exactly 16 stages matching `_STAGE_ORDER`
- **BAC-02**: `POST /api/v1/pipeline/run` returns 503 on FATAL preflight
- **BAC-03**: `POST /api/v1/pipeline/run` returns 202 with preflight key on OK/WARNING
- **BAC-04**: All 4 strategy presets correctly enable/disable the 3 new stages
- **BAC-05**: CHANGELOG.md updated
- **BAC-06**: All documents archived under `/docs/aiv/BATCH-172/`

---

## LEAD RESPONSE TO REVIEW REPORT

[Leave blank until Review Report received.]
