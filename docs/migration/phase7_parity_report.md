# Phase 7: Parity Report & Foundation Status

## Executive Summary

The sequential-operation refactoring (Phases 0–7) is structurally complete.
All new foundation components have failure-mode test coverage proving they
detect and reject incorrect states. Live parity validation against a running
LM Studio instance is **deferred** — LM Studio was not available during this
refactoring session.

---

## Test Baseline

| Metric | Phase 0 (start) | Phase 7 (current) | Delta |
|--------|-----------------|-------------------|-------|
| Failed | 63 | 59 | −4 (old failures fixed by overlay) |
| Passed | 3216 | 3350 | +134 |
| Skipped | 20 | 20 | 0 |
| Frontend passed | — | 353 | 24 new API client tests |

**Zero regressions**: The 59 baseline failures are all pre-existing test
assertions unrelated to the refactoring (stage count, form rendering,
routing contract, gateway enforcement). No code change in Phases 1–7
introduced a new failure.

---

## Phase-by-Phase Parity Status

### Phase 1: Operation Executor & Provider Conformance

**Status: Structural parity — deferred live validation**

- `OperationExecutor` wraps `LMStudioManager` with `asyncio.to_thread()`
- `build_receipt_from_response()` validates `served_model` against `requested_model`
- `StageExecutionResult` with no receipts is honestly marked `is_compatibility_mode = True`
- Orchestrator delegates model lifecycle to executor; stages still call providers internally

**Proven by failure-mode tests:**
- Wrong model served → `WrongModelServedError` ✅
- Missing receipt → `MissingModelReceiptError` ✅
- Stale cache reconciliation detects evicted model ✅
- Operation lock released after success and after error ✅
- Concurrent operations are serialized ✅

**Deferred:** Live LM Studio call comparing served model IDs.

### Phase 2: Durable Run Service

**Status: Fully tested with in-memory DB**

- UUID-based run IDs with DB uniqueness constraint
- Event outbox with per-run monotonic sequence
- Durable cancellation (survives restart)
- Worker lease with compare-and-set and heartbeat

**Proven by failure-mode tests:**
- Worker crash → orphan detected by heartbeat timeout ✅
- Orphaned run → new worker acquires lease ✅
- Cancellation persists across service restart ✅
- Double cancellation is idempotent ✅
- SSE replay from `Last-Event-ID` returns correct events ✅
- Worker lease compare-and-set prevents double-acquire ✅

### Phase 3: Orchestrator Decomposition

**Status: Structural parity — deferred live validation**

- Stage loop extracted to `RunCoordinator` (strategy skip, doom skip, routing cascade, executor delegation, policy gate, heartbeat, checkpoint, cancel check)
- Factory extracted to `CompositionRoot`
- Bridge method `execute_with_result()` on `StageExecutor`
- Orchestrator: 1681 → 1366 lines

**Deferred:** Live pipeline run comparing stage completion, idea counts,
and novelty outputs between old and new orchestrator paths.

### Phase 4: Crash-Safe Persistence & Replay

**Status: Fully tested**

- Atomic checkpoint writes: temp-file → `flush()` → `fsync()` → `os.replace()`
- Schema versioning: `CHECKPOINT_SCHEMA_VERSION = 2`, incompatible versions rejected
- Typed errors: `CheckpointPersistenceError`, `IncompatibleCheckpointError`
- Replay idempotency: `content_hash(run_id|title|problem_statement)` stored as idempotency key

**Proven by tests:**
- Interrupted write preserves old checkpoint ✅
- Corrupted checkpoint raises typed error ✅
- Schema version mismatch raises typed error ✅
- Replay does not duplicate ideas ✅
- Collector links preserved through replay ✅

### Phase 5: Security & Fail-Closed Critical Paths

**Status: Fully tested**

- Production config refuses default JWT secret, wildcard CORS, auth disabled, noop sandbox
- WebSocket auth: query-string token removed, first-message auth only
- Embedding fail-closed: provider failure raises `EmbeddingProviderError`, zero vectors rejected
- Exception discipline: RunService has zero broad `except Exception` handlers

**Proven by tests:**
- All insecure defaults rejected in production mode ✅
- WebSocket endpoint signature has no `token` query param ✅
- Embedding provider failure → typed error (not zero vectors) ✅
- Zero vector from provider → typed error ✅
- `save_checkpoint` raises (not warning-only) ✅

### Phase 6: Frontend Consolidation

**Status: Fully tested (24 frontend tests)**

- `client.ts` is the single owner of `localStorage` API URL/key reads
- `apiFetchBlob()` for binary exports, `apiFetchFormData()` for PDF ingestion
- `sseFetch()` with `Last-Event-ID` header for durable replay
- `usePipelineProgress` uses SSE + REST polling fallback
- Zero `localStorage.getItem('erock_api_*')` calls outside `client.ts`

**Deferred (documented risk):** localStorage token/API-key hardening
(not part of this phase's scope).

---

## Coverage

- Total backend coverage: **67%** (threshold: 72%)
- `backend/api/*` included in coverage since Phase 2
- `backend/tests/*` and `backend/cli/*` omitted
- The 72% threshold is not met but was not met at baseline either
- The new code paths (operations, run_service, persistence) have dedicated
  test suites with >90% coverage of their public interfaces

**Recommendation:** Do not raise the threshold until the 59 pre-existing
test failures are addressed. The new code is well-tested; the gap is in
legacy code that this refactoring intentionally did not touch.

---

## Deferred Live Parity Validation

If LM Studio becomes available, run this golden scenario:

1. **Start a pipeline run** with a known domain and strategy
2. **Compare stage completion order** — all 10 stages must complete in the same order
3. **Compare idea counts** — same `ideas_per_round` must produce the same number of ideas
4. **Compare novelty scores** — scores must be within ±0.05 of baseline
5. **Compare export output** — PDF export must contain the same sections
6. **Verify ModelReceipt chain** — every stage must produce receipts with correct `served_model`

Until then, structural parity (code paths traceable, behavior preserved,
no new failures) is the current guarantee.

---

## Carried Debt (Unchanged from Earlier Phases)

1. Process-local globals (`_cancel_events`, `_progress_queues`) for autonomous cycles and session resume
2. `_override_provider` mutation pattern (6 call sites in `stages.py`)
3. Full `__init__` → `CompositionRoot` migration (gateway/services wiring needs orchestrator self-reference)
4. 2304 ruff errors (pre-existing formatting/lint)
5. localStorage token/API-key hardening (frontend)
