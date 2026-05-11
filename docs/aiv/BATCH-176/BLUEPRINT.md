# BATCH BLUEPRINT — BATCH-176

Batch ID:                 BATCH-176
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-11
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing: Sequential

---

## BATCH GOAL

Add provider-level retry with exponential backoff for HTTP 429 (rate limit) and 503
(service unavailable) errors. Surface retry count in the stage_report. Add a
configurable `llm_rate_limit_retries` setting. When all retries are exhausted,
the stage falls through to the existing `skipped_by_error` handler from B173.

---

## SCOPE STATEMENT

**What the code MUST do:**
- Add a `retry_llm_call()` wrapper function in `backend/providers/provider_factory.py` (or a new `backend/providers/retry.py`) that wraps any `async def` LLM call with exponential backoff on 429/503
- Backoff sequence: 2s, 4s, 8s (configurable via `llm_rate_limit_retries` setting, default 3)
- Detect 429/503 by catching `Exception` and checking for status code in the exception message or exception attributes (Anthropic SDK raises `anthropic.RateLimitError` and `anthropic.APIStatusError`; OpenAI raises `openai.RateLimitError`)
- Add `llm_rate_limit_retries: int = 3` to `backend/config.py` Settings
- Add `retries_used: int = 0` field to `StageReport` dataclass in `backend/pipeline/result.py`
- In `_execute_stage_with_retry()`, track how many retries were consumed by provider-level retries and pass that count to the StageReport
- The retry wrapper must log each retry attempt at WARNING level

**What the code MUST NOT do:**
- MUST NOT change the behavior of successful LLM calls (zero overhead on happy path)
- MUST NOT remove the existing stage-level retry in `_execute_stage_with_retry`
- MUST NOT add provider-specific imports at the module level (use lazy imports inside except blocks)
- MUST NOT increase total pipeline latency on successful runs

---

## LINT COMMAND

```
python -m pytest backend/tests/test_pipeline/test_batch176_*.py -v --tb=short -p no:asyncio
```

---

## HARD BOUNDARIES

- **HB-01**: Successful LLM calls must have zero overhead — the retry wrapper must not add async sleep or logging on success
- **HB-02**: After exhausting all retries, the original exception must propagate (not a generic "retries exhausted" message) so the stage error handler gets the real error
- **HB-03**: The `llm_rate_limit_retries` setting must be 0-testable — setting it to 0 means no retries (fail immediately on 429)

---

## DATA MODELS / SCHEMA

**New file: `backend/providers/retry.py`**
```python
async def retry_llm_call(coro, max_retries: int = 3, base_delay: float = 2.0) -> tuple[Any, int]:
    """Wrap an LLM coroutine call with exponential backoff on 429/503.
    Returns (result, retries_used)."""
```

**Modified: `backend/pipeline/result.py`**
```python
@dataclass
class StageReport:
    name: str
    status: str
    elapsed_s: float = 0.0
    error: str | None = None
    skip_reason: str | None = None
    retries_used: int = 0  # NEW: provider-level retry count
```

**Modified: `backend/config.py`**
```python
llm_rate_limit_retries: int = 3  # NEW: max retries on 429/503
```

**Modified: `backend/pipeline/orchestrator.py`**
- In the stage execution block, after `_execute_stage_with_retry` returns, track `retries_used`

---

## AUTHORITY RULES

- **AUTH-01**: Only 429 and 503 trigger retries — all other exceptions propagate immediately
- **AUTH-02**: The retry delay must use exponential backoff: `base_delay * 2^attempt` (2s, 4s, 8s)
- **AUTH-03**: `retries_used` on StageReport is informational only — it does not affect stage status

---

## DEPENDENCY MAP

- BATCH-173 (StageReport) — CLOSED
- `backend/providers/anthropic_provider.py` — READ ONLY (retry wrapper wraps calls externally)
- `backend/providers/provider_factory.py` — will be modified or new file created alongside

---

## STATE.md STATUS

- State file exists: YES
- Last Updated: 2026-05-11 (BATCH-175)
- Batches since update: 0

---

## TEST BASELINE

- Baseline at Blueprint issuance: **2,826** tests
- Expected delta (all Tasks): **+10** new tests
- Expected total at Batch close: **2,836**

---

## TASK LIST

### TASK-01: BATCH-176/TASK-01 — Retry Wrapper + Config + StageReport Field
- **Priority:** Critical
- **Description:** Create `backend/providers/retry.py` with `retry_llm_call()`. Add `retries_used` to StageReport. Add `llm_rate_limit_retries` to config. Wire retry into orchestrator stage execution.
- **Files in scope:** `backend/providers/retry.py` (NEW), `backend/pipeline/result.py`, `backend/config.py`, `backend/pipeline/orchestrator.py`
- **Depends on:** None

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-176-01-01 | unit | `retry_llm_call` returns result on success | Always retries | Set threshold to 0 | Returns correct result, retries_used=0 |
| TEST-176-01-02 | unit | `retry_llm_call` retries on 429 | No retry | Return immediately | `retries_used > 0`, eventual success |
| TEST-176-01-03 | unit | `retry_llm_call` retries on 503 | No retry | Return immediately | `retries_used > 0`, eventual success |
| TEST-176-01-04 | unit | `retry_llm_call` propagates after max retries exhausted | Silent fail | Catch and return None | Exception raised after 3 retries |
| TEST-176-01-05 | unit | `retry_llm_call` with max_retries=0 fails immediately | Still retries | Ignore setting | Exception on first 429, no sleep |
| TEST-176-01-06 | unit | StageReport has retries_used field | Missing field | Remove field | `hasattr(report, 'retries_used')` |
| TEST-176-01-07 | unit | Config has llm_rate_limit_retries | Missing setting | Remove from config | `hasattr(settings, 'llm_rate_limit_retries')` and default=3 |

**Acceptance Criteria:**
- AC-01-01: retry_llm_call works with zero overhead on success
- AC-01-02: 429/503 trigger retries with backoff
- AC-01-03: Exhausted retries propagate original exception
- AC-01-04: StageReport has retries_used
- AC-01-05: Config has llm_rate_limit_retries

**Traceability:** AC-01-01→T-01 | AC-01-02→T-02,T-03 | AC-01-03→T-04,T-05 | AC-01-04→T-06 | AC-01-05→T-07

---

### TASK-02: BATCH-176/TASK-02 — Integration + Verification + Batch Close
- **Priority:** High
- **Description:** Write integration test verifying retry works in pipeline context. Verify no regressions. Update STATE.md and CHANGELOG.
- **Files in scope:** NEW FILE `backend/tests/test_pipeline/test_batch176_retry.py`, `docs/aiv/STATE.md`, `CHANGELOG.md`
- **Depends on:** TASK-01

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-176-02-01 | integration | Stage with retrying provider eventually succeeds | Stuck retrying | Infinite loop | Stage reports "executed" with retries_used > 0 |
| TEST-176-02-02 | integration | Stage with exhausted retries gets skipped_by_error | Pipeline crashes | Exception propagates | Stage reports "skipped_by_error" with error containing "429" |
| TEST-176-02-03 | integration | No regressions in batch172-175 | Regression | Revert wiring | Subprocess check passes |
| TEST-176-02-04 | unit | STATE.md has BATCH-176 | Stale | Check content | `"BATCH-176" in content` |
| TEST-176-02-05 | unit | CHANGELOG has BATCH-176 | Missing | Check content | `"BATCH-176" in content` |

**Acceptance Criteria:**
- AC-02-01: Integration tests pass for retry success and failure scenarios
- AC-02-02: No regressions
- AC-02-03: STATE.md and CHANGELOG updated

**Traceability:** AC-02-01→T-01,T-02 | AC-02-02→T-03 | AC-02-03→T-04,T-05

---

## BATCH-LEVEL ACCEPTANCE CRITERIA

- **BAC-01**: LLM calls retry on 429/503 with exponential backoff
- **BAC-02**: Successful calls have zero overhead
- **BAC-03**: StageReport includes retries_used
- **BAC-04**: Config has llm_rate_limit_retries setting
- **BAC-05**: CHANGELOG.md updated
- **BAC-06**: All documents archived under `/docs/aiv/BATCH-176/`

---

## LEAD RESPONSE TO REVIEW REPORT

[Leave blank until Review Report received.]
