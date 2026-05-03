# BATCH-57 BLUEPRINT — Pipeline Polish & DB Schema Sync

**Lead Programmer:** Lead Agent  
**Date:** 2026-05-03  
**AIV Framework:** v5.2  
**Cycle Mode:** Standard (2 Tasks)

---

## Context

Pipeline retest (BATCH-56) revealed the pipeline ACTUALLY WORKS — Run 15 completed with 2 ideas, 2 gaps, 102 papers. But several polish issues remain:

1. **DB schema migration gaps** — Model defines columns that don't exist in SQLite (model evolves faster than migrations)
2. **`completed_at` NULL** on completed runs — persistence layer doesn't set it reliably  
3. **`stages_completed` empty** — orchestrator doesn't persist stage progress

---

## TASK-01: Fix DB Schema Sync

### Problem
The DB was created via `create_all()` from an older model snapshot. New columns added in later batches don't exist:
- `ideas` table missing columns that may be needed by future features
- Model and DB are out of sync

### Fix
Add an `ensure_schema_sync()` function to `backend/db/database.py` that:
1. Uses SQLAlchemy `inspect()` to get actual DB columns
2. Compares against model metadata
3. Adds missing columns via `ALTER TABLE ADD COLUMN`
4. Called during app startup (in `init_db()`)

This is a pragmatic approach — Alembic migrations handle versioned deployments, but `ensure_schema_sync()` catches developer-mode gaps where `create_all()` was used.

### Target Files
- `backend/db/database.py` — Add `ensure_schema_sync()`
- `backend/db/models.py` — No changes needed

### Tests
- Test that `ensure_schema_sync()` adds missing columns
- Test that it's idempotent (no error on re-run)

---

## TASK-02: Fix Pipeline Completion Metadata

### Problem
Completed runs have:
- `completed_at = NULL` — should be set when status transitions to "completed"
- `stages_completed = []` — should track which stages ran
- `current_stage` stays at "initializing" — should show the last completed stage

### Fix
In `backend/pipeline/persistence.py` or `backend/db/crud.py`:

1. `mark_run_completed()` must set `completed_at = datetime.now(timezone.utc)`
2. `mark_run_completed()` must set `current_stage` to the final stage name
3. Add an `advance_stage(run_id, stage_name)` method that appends to `stages_completed` and updates `current_stage`

Then in `backend/pipeline/orchestrator.py`:
4. Call `advance_stage()` at each stage transition
5. Call `mark_run_completed()` with proper metadata at the end

### Target Files
- `backend/pipeline/persistence.py` — Fix completion metadata
- `backend/pipeline/orchestrator.py` — Add stage tracking calls

### Tests
- Test completed run has non-null `completed_at`
- Test `stages_completed` is populated
- Test `advance_stage()` works

---

## Acceptance Criteria

| Criterion | Verification |
|:---|:---|
| `ensure_schema_sync()` adds missing columns | Test assertion |
| `ensure_schema_sync()` is idempotent | Test assertion |
| Completed runs have `completed_at` set | DB query |
| `stages_completed` tracks pipeline progress | DB query |
| All 1,829 existing tests still pass | pytest + vitest |

---

*BLUEPRINT — BATCH-57 — AIV Framework v5.2 — Lead Agent*
