# Phase 2 Carried Debt: Remaining Non-Durable Lifecycle Paths

**Date:** 2026-06-16
**Status:** Tracked — migrate before Phase 5 security hardening

## What

Process-local globals (`_cancel_events`, `_progress_queues`, `_background_tasks`) remain in `backend/api/routes/pipeline.py` for these paths:

| Path | Lines | Issue |
|------|-------|-------|
| Autonomous cycle (`start_autonomous_cycle`) | ~636-692 | Uses `_progress_queues[cycle_id]` and `_cancel_events[cycle_id]` for progress streaming and cancellation |
| Session resume (`resume_session`) | ~1003-1355 | Uses `_progress_queues[run_id]` and `_cancel_events[run_id]` |
| Autonomous stop (`stop_autonomous_cycle`) | ~724-739 | Uses `_cancel_events.get(cycle_id)` |

## Why deferred

Phase 2 migrated the primary pipeline run lifecycle (`trigger_run` → `progress` → `cancel`). The autonomous cycle and session resume paths are secondary and have different lifecycle semantics (multi-run coordination, checkpoint reconstruction). Migrating them requires extending `RunService` to support cycle-level grouping, which is not Phase 2 scope.

## Risk

Low — these paths are used less frequently and don't affect the core pipeline execution contract. However, they cannot survive process restart, which is a durability gap.

## Plan

1. Extend `RunService` to support cycle-level grouping (or a separate `CycleService`)
2. Migrate autonomous cycle to durable pattern
3. Migrate session resume to durable pattern
4. Remove `_cancel_events`, `_progress_queues`, `_background_tasks` globals entirely
5. Verify no test references these globals
