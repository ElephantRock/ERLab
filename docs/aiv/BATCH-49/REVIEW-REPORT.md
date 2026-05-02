# BATCH-49 REVIEW REPORT — Notification Center + Experiment Runner

**Reviewer:** Reviewer Agent  
**Date:** 2026-05-03  
**AIV Framework:** v5.1  
**Blueprint:** `docs/aiv/BATCH-49/BLUEPRINT.md`  
**Status:** ✅ APPROVED WITH CONDITIONS

---

## Executive Summary

The Blueprint defines two well-scoped tasks: (1) a user-facing notification center with SSE real-time push, and (2) a sandboxed experiment execution runner. The plan is architecturally sound and aligns with existing codebase patterns. Three issues require resolution before implementation begins; four recommendations are advisory.

---

## CHK-01: Referenced Files — Existence & Accuracy

| Blueprint Reference | Exists | Notes |
|:---|:---:|:---|
| `backend/db/models.py` | ✅ | All models confirmed (User, Paper, Idea, Proposal, PipelineRun, Comment, SharedIdea, ResearchGapDB) |
| `backend/api/app.py` | ✅ | Route registration pattern confirmed: `app.include_router(...)` with `prefix`, `tags`, `dependencies=_auth` |
| `backend/notifications/webhooks.py` | ✅ | BATCH-32 webhook dispatcher. Async `fire_webhook(event_type, payload)` function |
| `backend/notifications/__init__.py` | ✅ | Exports `fire_webhook` only — new `dispatch.py` must be added to exports |
| `backend/pipeline/sandboxing/` | ✅ | 3 backends: `docker_backend.py`, `subprocess_backend.py`, `noop_backend.py` + `manager.py` + `protocol.py` |
| `backend/config.py` | ✅ | `Settings(BaseSettings)` with `EROCK_` env prefix. `@functools.lru_cache` singleton via `get_settings()` |
| `backend/api/routes/pipeline.py` | ✅ | Webhook dispatch pattern confirmed at lines 85–100 (completion) and 105–115 (failure) |
| `alembic/versions/` | ✅ | 4 existing migrations: `001_initial`, `002_gap_enrichment`, `003_gap_feedback`, `004_gap_dedup` |
| `frontend/src/api/types.ts` | ✅ | Interface export pattern confirmed |
| `frontend/src/api/client.ts` | ✅ | `apiFetch<T>()` + `sseFetch()` utilities confirmed |
| `frontend/src/components/layout/app-shell.tsx` | ✅ | Header bar at `<div className="flex items-center gap-2 border-b px-4 h-10">` — line for bell integration confirmed |

**Verdict: ✅ PASS** — All referenced files exist and descriptions are accurate.

---

## CHK-02: Data Model Accuracy

### NotificationDB Model Verification

| Blueprint Spec | Codebase Convention | Match? |
|:---|:---|:---:|
| `id: int PK` | `id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)` | ✅ Must use `Mapped[int]` + `mapped_column()` |
| `user_id: int FK → users.id (nullable)` | FK pattern: `mapped_column(Integer, ForeignKey("users.id"), nullable=True)` | ✅ Pattern exists (see `Idea.pipeline_run_id`) |
| `type: String(50)` | `Mapped[str] = mapped_column(String(50))` | ✅ |
| `title: String(255)` | `Mapped[str] = mapped_column(String(255))` | ✅ |
| `message: Text` | `Mapped[str] = mapped_column(Text)` | ✅ |
| `read: Boolean default False` | `Mapped[bool] = mapped_column(Boolean, default=False)` | ✅ |
| `created_at: DateTime default utcnow` | **⚠️ ISSUE-01** — see below | ⚠️ |
| Indexes via `__table_args__` | Pattern: `__table_args__ = (Index("ix_...", "col"), ...)` | ✅ |

### ISSUE-01: DateTime Default Pattern

The Blueprint specifies `default utcnow` but all existing models use:
```python
created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
```
The Blueprint notation is pseudo-code and acceptable, but the **implementer must use the `lambda: datetime.now(timezone.utc)` pattern** for consistency. Not a blocker — documented here for implementer awareness.

### ExperimentResult Model

The Blueprint defines `ExperimentResult` as a **Pydantic BaseModel** (not an ORM model). This is correct — it's a response schema, not a persisted entity. The existing codebase uses Pydantic models for API schemas (see `backend/api/schemas.py`). ✅

### Migration 005

The naming convention `005_notifications` follows the established pattern (`004_gap_dedup`, `003_gap_feedback`, etc.). The `down_revision` must be `"004_gap_dedup"`. Uses `batch_alter_table` for SQLite compatibility — confirmed from existing migrations. ✅

**Verdict: ✅ PASS** — Data models align with codebase conventions. ISSUE-01 is advisory, not a blocker.

---

## CHK-03: Code Pattern Conflicts

### Route Registration

The Blueprint specifies mounting notification routes at `/api/v1/notifications`. Existing pattern:
```python
app.include_router(
    notifications.router, prefix="/api/v1/notifications", tags=["notifications"], dependencies=_auth
)
```
No conflict — no existing route uses `/api/v1/notifications`. ✅

Similarly, experiment routes at `/api/v1/experiments` — no conflict. ✅

**ISSUE-02: Auth requirement for SSE stream**

The Blueprint specifies `GET /api/v1/notifications/stream` as an SSE endpoint. The existing SSE pattern in `pipeline.py` (the `run_progress` endpoint) performs **defence-in-depth auth validation** inside the handler (lines 299–315). The notification SSE stream must follow this same pattern if JWT auth is enabled. The Blueprint doesn't mention this explicitly — implementer should mirror the pipeline SSE auth pattern.

### Webhook Integration Points

The Blueprint says to wire `create_notification()` into existing pipeline hooks. Current hook locations in `backend/api/routes/pipeline.py`:
- **pipeline.completed**: Lines 85–100 — calls `fire_webhook("pipeline.completed", ...)` after orchestrator completes
- **pipeline.failed**: Lines 105–115 — calls `fire_webhook("pipeline.failed", ...)` in the except block

The `create_notification()` call should be placed alongside each `fire_webhook()` call. Both should be wrapped in try/except (notification failures must not block the pipeline — HB-01 principle). ✅ Pattern is clear.

### Notification Dispatch Module

**ISSUE-03: SSE Stream Architecture**

The Blueprint specifies an SSE stream in `backend/api/routes/notifications.py` and a push mechanism in `backend/notifications/dispatch.py`. This requires a shared state mechanism (e.g., an `asyncio.Queue` per connected client, or a pub/sub pattern). The existing pipeline progress SSE uses module-level `_progress_queues: dict[str, asyncio.Queue]`. The notification SSE will need a similar but **global** queue (all users share one stream, or per-user queues for filtered delivery).

The Blueprint is not explicit about the pub/sub mechanism. Recommend:
- Use a module-level `set[asyncio.Queue]` in `dispatch.py` for connected SSE clients
- `create_notification()` pushes to all queues
- Each SSE handler registers its queue on connect, deregisters on disconnect

This is a design gap but not a blocker — implementer will need to make an architectural choice.

### Sandboxing Integration

The Blueprint says `ExperimentRunner` "uses existing `backend/pipeline/sandboxing/` Docker backend for isolation." Verified:
- `SandboxManager.execute_python(code, config)` → `ExecutionResult(exit_code, stdout, stderr, timed_out, duration_seconds)` ✅
- `ExecutionResult` is a Pydantic model with the fields the Blueprint's `ExperimentResult` needs ✅
- The mapping is straightforward: `ExecutionResult` → `ExperimentResult` with additional `artifacts`, `metrics`, `error` fields

The Blueprint's `ExperimentResult` extends the sandbox `ExecutionResult` with `artifacts`, `metrics`, and `error`. This is clean layering. ✅

### Config Parameters

The Blueprint adds 3 new config parameters:
```python
experiment_enabled: bool = False
experiment_timeout: int = 30
experiment_max_code_size: int = 10000
```

**ISSUE-04: Config parameter naming inconsistency**

Existing sandbox config uses `sandbox_default_timeout` (float, 30.0) while the Blueprint proposes `experiment_timeout` (int, 30). Consider aligning types (`float` vs `int`) and naming (`experiment_default_timeout` to match `sandbox_default_timeout` pattern). Minor — not a blocker.

**Verdict: ⚠️ PASS WITH CONDITIONS** — Issues 02–04 are non-blocking but should be addressed during implementation.

---

## CHK-04: Task Scope Assessment

### TASK-01: Notification Center

| Component | Complexity | Assessment |
|:---|:---:|:---|
| NotificationDB model + migration | Low | Standard model, follows existing patterns |
| CRUD route module (4 endpoints) | Medium | GET list, PATCH read, POST read-all, SSE stream |
| Dispatch helper + hook wiring | Medium | 4 hook points, SSE push mechanism |
| Frontend API client + types | Low | 3 functions + 1 interface |
| NotificationBell component | Low | Icon + badge count + dropdown |
| NotificationList component | Medium | Paginated list + mark-all-read |
| AppShell integration | Low | Single import + placement |
| Tests (10 total) | Medium | 6 backend + 4 frontend |

**Verdict: ✅ Well-scoped.** This is a full-stack feature but each piece is small. Estimated effort: moderate.

### TASK-02: Sandboxed Experiment Execution

| Component | Complexity | Assessment |
|:---|:---:|:---|
| ExperimentRunner | Medium | Wraps existing SandboxManager |
| ExperimentResult (Pydantic) | Low | Simple response model |
| SecurityValidator | Medium | AST-based code analysis for dangerous patterns |
| Routes (2 endpoints) | Low | POST run + GET cached result |
| Config (3 params) | Low | Standard Settings additions |
| Tests (4 total) | Medium | Security + execution + timeout |

**Verdict: ✅ Well-scoped.** Backend-only, leverages existing sandboxing infrastructure. Clean API-first approach.

---

## CHK-05: Dependency Analysis

### Inter-Task Dependencies

```
TASK-01 (Notifications) ──── Independent ──── can start immediately
TASK-02 (Experiments)  ──── Independent ──── can start immediately
```

Both tasks are **fully independent** — no shared code, no shared models, no shared migrations. They can be developed in parallel. ✅

### Intra-Task Dependencies

**TASK-01 chain:**
```
NotificationDB model → Migration 005 → Route module → Dispatch helper → Hook wiring
                                                                              ↓
                                                     Frontend types → API client → Components → AppShell integration
```

All dependencies are linear and correctly implied by the Blueprint. ✅

**TASK-02 chain:**
```
SecurityValidator → ExperimentRunner → Route module
Config params ─────────────────────────↑
```

Dependencies are correct. The validator must be complete before the runner can use it. ✅

### External Dependencies

| Dependency | Status |
|:---|:---|
| Alembic migration chain (`004_gap_dedup` → `005_notifications`) | ✅ Sequential, no conflict |
| `backend/notifications/__init__.py` must be updated to export `create_notification` | ⚠️ Blueprint doesn't mention this — implementer must do it |
| `backend/api/app.py` import section must add 2 new route modules | ✅ Standard pattern |
| Docker must be available for experiment execution tests | ⚠️ CI/CD consideration — tests should handle Docker unavailable gracefully |

**Verdict: ✅ PASS** — Dependencies are correctly identified. Minor items noted for implementer.

---

## CHK-06: Test Requirements

### TASK-01 Tests (Blueprint: 10 tests)

| Test | Coverage | Sufficient? |
|:---|:---|:---:|
| Notification CRUD | Create, read, update | ✅ |
| SSE stream | Real-time push | ✅ |
| Read/unread filtering | Query params | ✅ |
| Mark-all-read | Bulk update | ✅ |
| Bell renders | Component mount | ✅ |
| Badge shows count | Unread count display | ✅ |
| Click marks read | User interaction | ✅ |
| *(implied)* List pagination | Not explicitly listed | ⚠️ **GAP** |

**GAP-01:** The Blueprint claims "+6 backend tests" but doesn't explicitly list a pagination test. The `GET /api/v1/notifications/` endpoint supports pagination — at minimum, verify `limit`/`offset` parameters work correctly.

**GAP-02:** No test for the `user_id: null` broadcast scenario. If `user_id` is null (broadcast), does `GET /notifications/` return broadcast notifications to all users? This edge case should be tested.

**GAP-03:** No test for SSE reconnection behavior. What happens if a client disconnects and reconnects? Are missed notifications recoverable via the paginated GET endpoint? (This is a design question as much as a test question.)

### TASK-02 Tests (Blueprint: 4 tests)

| Test | Coverage | Sufficient? |
|:---|:---|:---:|
| Validator blocks dangerous code | Security | ✅ |
| Validator allows safe code | Security | ✅ |
| Runner returns structured result | Execution | ✅ |
| Timeout enforced | Resource limit | ✅ |

**GAP-04:** No test for `experiment_enabled=False` guard. When disabled, `POST /api/v1/experiments/run` should return an appropriate error. This is a config gate test.

**GAP-05:** No test for `experiment_max_code_size` enforcement. The config limits code to 10KB — should be tested with oversized input.

**GAP-06:** No test for the Docker-unavailable fallback. When Docker is not running, the experiment runner should return a clear error (not a 500).

**Verdict: ⚠️ PASS WITH CONDITIONS** — Core test coverage is adequate but 6 gaps identified. Gaps 01–02 are recommended additions; Gaps 03–06 are optional but improve robustness.

---

## Summary of Issues & Recommendations

### Issues (Must Address)

| # | Severity | Description | Action |
|:---|:---:|:---|:---|
| ISSUE-01 | Low | DateTime default must use `lambda: datetime.now(timezone.utc)` pattern | Implementer note |
| ISSUE-02 | Medium | SSE stream must include defence-in-depth auth check (mirror pipeline.py pattern) | Implementer must add |
| ISSUE-03 | Medium | SSE pub/sub mechanism not specified — implementer must design shared queue architecture | Recommend global `set[asyncio.Queue]` in dispatch.py |
| ISSUE-04 | Low | Config naming inconsistency (`experiment_timeout` vs `sandbox_default_timeout` pattern) | Consider `experiment_default_timeout: float = 30.0` |

### Recommendations (Advisory)

| # | Description |
|:---|:---|
| REC-01 | Update `backend/notifications/__init__.py` to export `create_notification` from new `dispatch.py` |
| REC-02 | Add notification dispatch calls to `gap.found` and `idea.generated` hook points (currently only pipeline.py has webhook hooks; gap/idea creation happens inside the orchestrator) |
| REC-03 | Consider adding a `notifications` table cleanup mechanism (e.g., TTL or archive) for production — the table will grow unbounded otherwise |
| REC-04 | The `GET /api/v1/experiments/{id}` cached result endpoint stores results "in memory" — consider whether this should use a TTL cache to prevent memory leaks |

---

## Final Verdict

| Check | Result |
|:---|:---|
| CHK-01: File references | ✅ PASS |
| CHK-02: Data model accuracy | ✅ PASS |
| CHK-03: Code pattern conflicts | ⚠️ PASS WITH CONDITIONS (Issues 02–03) |
| CHK-04: Task scope | ✅ PASS |
| CHK-05: Dependencies | ✅ PASS |
| CHK-06: Test requirements | ⚠️ PASS WITH CONDITIONS (Gaps 01–02) |

**Overall: ✅ APPROVED FOR IMPLEMENTATION**

The Blueprint is sound. Issues 02–03 require implementer attention during TASK-01 development. Test gaps 01–02 should be addressed in the test plan. All other items are advisory.

---

*REVIEW-REPORT — BATCH-49 — AIV Framework v5.1 — Reviewer Agent*
