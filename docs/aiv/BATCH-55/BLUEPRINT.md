# BATCH-55 BLUEPRINT — Fix Pipeline Execution Critical Bugs

**Lead Programmer:** Lead Agent  
**Date:** 2026-05-03  
**AIV Framework:** v5.2  
**Status:** DRAFT  
**Cycle Mode:** Standard (3 Tasks)

---

## Context

BATCH-54 UX E2E test discovered that pipeline runs never complete — 10 runs stuck in `status=running`. Two critical bugs identified:

1. **Pipeline background task fails silently** — The `_run_pipeline()` async task in `pipeline.py` catches exceptions and logs them, but the orchestrator's `run()` method uses `self._persistence.mark_run_failed()` which may itself fail if the session factory has issues. The error path does not update the DB status reliably.

2. **`GET /api/v1/pipeline/runs` crashes with INTERNAL_ERROR** — The `list_runs` endpoint uses `with get_session()` (sync context manager) inside an `async def`. The session may be closed before the lazy-loaded `r.ideas` relationship is accessed, causing a `DetachedInstanceError`.

---

## TASK-01: Fix Pipeline Background Task Error Handling

### Target File: `backend/api/routes/pipeline.py`

### Problem
The `_run_pipeline()` function in `trigger_run()` catches `Exception` and fires webhooks/notifications, but never calls `persistence.mark_run_failed()` on the DB run record. The orchestrator's own `run()` method handles internal failures via `self._persistence.mark_run_failed()` at line 1079, but if the exception occurs BEFORE the orchestrator creates the DB record (or AFTER the orchestrator's internal error handling), the status stays "running" forever.

### Fix
In the `_run_pipeline()` function's `except` block, add a direct DB update to mark the run as failed:

```python
except Exception as e:
    logger.error("Pipeline run %s failed: %s", run_id, e)
    # Directly update DB status to failed (the orchestrator may not have done it)
    try:
        from backend.db.database import get_session as _get_db_session
        from backend.db.models import PipelineRun
        with _get_db_session() as db_session:
            run_record = db_session.query(PipelineRun).filter(
                PipelineRun.session_id == request.session_id
            ).order_by(PipelineRun.id.desc()).first()
            if run_record and run_record.status == "running":
                run_record.status = "failed"
                run_record.error_message = str(e)[:500]
                run_record.completed_at = datetime.now(timezone.utc)
                db_session.commit()
    except Exception as db_err:
        logger.warning("Failed to mark run as failed in DB: %s", db_err)
    # ... existing webhook/notification code ...
```

Also add a safety check in `list_runs` to handle detached sessions.

### Tests
- Test that a failed pipeline run gets status="failed" in DB
- Test that error_message is populated on failure
- Test that completed_at is set on failure

---

## TASK-02: Fix list_runs Serialization Crash

### Target File: `backend/api/routes/pipeline.py`

### Problem
The `list_runs` endpoint accesses `r.ideas` (a lazy-loaded relationship) after the `with get_session()` context closes. This causes `DetachedInstanceError` because SQLAlchemy closes the session when the context manager exits.

### Fix
Eagerly load the `ideas` relationship, or build the response inside the context manager:

```python
async def list_runs(...):
    from backend.db.crud import list_pipeline_runs, count_pipeline_runs
    from backend.db.database import get_session

    with get_session() as session:
        runs = list_pipeline_runs(session, limit=limit, offset=offset, session_id=session_id)
        total = count_pipeline_runs(session, session_id=session_id)
        # Build response INSIDE the session context to avoid DetachedInstanceError
        run_list = []
        for r in runs:
            run_list.append({
                "id": r.id,
                "status": r.status,
                "domain": r.domain,
                "current_stage": r.current_stage,
                "ideas_count": len(r.ideas),  # Access while session is open
                "session_id": r.session_id,
                "created_at": str(r.created_at),
                "completed_at": str(r.completed_at) if r.completed_at else None,
                "error_message": r.error_message,
            })
        return {"runs": run_list, "total": total}
```

The key change: build `run_list` inside the `with` block. The current code builds the list comprehension inside the `return` statement, which should be fine since it's still inside the `with` block — but the actual crash suggests the `get_session()` generator may not be yielding properly in the async context. Let me verify.

Actually, reading the code more carefully: `get_session()` is a sync `@contextmanager` used in `async def`. This works because the context manager enters/exits synchronously, but the `session.close()` in `finally` may conflict with SQLAlchemy's async expectations. The fix is to use `next(get_session())` pattern or to ensure the session stays open through the entire response serialization.

The simplest fix: make `get_session` work properly with async by converting to an async generator, OR wrap the session usage in `await asyncio.to_thread()`, OR just ensure the response dict is fully built before the context exits (which the current code does — the crash may be from something else).

Let me check: the crash could also be from `list_pipeline_runs()` or `count_pipeline_runs()` failing internally.

### Fix Strategy
1. Add error logging to `list_runs` to capture the actual exception
2. Wrap the DB access in a try/except to return a meaningful error instead of INTERNAL_ERROR
3. If the issue is the sync context manager in async, convert `get_session()` to async-compatible pattern

### Tests
- Test that `GET /runs` returns 200 (not 500)
- Test with runs that have ideas (verify ideas_count works)
- Test with runs that have no ideas

---

## TASK-03: Add Frontend Stale Run Detector

### Target Files: `frontend/src/pages/run-detail.tsx`, `frontend/src/pages/dashboard.tsx`

### Specification

Add a visual indicator when a run has been in "running" status for more than 5 minutes:

1. In `run-detail.tsx`: If the run's `created_at` is more than 5 minutes ago and status is still "running", show a yellow banner:
   > ⚠️ This run has been running for over 5 minutes. It may have encountered an issue. You can try refreshing or starting a new run.

2. In `dashboard.tsx`: Show a small warning icon next to any run that's been "running" for >5 minutes.

3. Implementation:
   - Use `new Date(run.created_at)` and compare with `Date.now()`
   - Check every 30 seconds with a `setInterval` (clean up on unmount)
   - The 5-minute threshold is hardcoded for now (no config needed)

### Tests
- Run detail page shows warning for stale runs (>5 min "running")
- Dashboard shows warning icon for stale runs
- No warning for completed or recently started runs

---

## Acceptance Criteria

| Criterion | Verification |
|:---|:---|
| Failed pipeline run gets status="failed" in DB | Test assertion |
| error_message populated on failure | Test assertion |
| `GET /runs` returns 200 (not 500) | curl test |
| ideas_count works for runs with ideas | Test assertion |
| Stale run warning shows after 5 minutes | Frontend test |
| All existing tests pass | pytest + vitest |

---

*BLUEPRINT — BATCH-55 — AIV Framework v5.2 — Lead Agent*
