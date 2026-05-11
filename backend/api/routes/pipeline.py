"""Pipeline API routes."""

import asyncio
import contextlib
import json
import logging
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request, Depends
from fastapi.responses import StreamingResponse

from backend.api.auth import verify_api_key
from backend.api.errors import NotFoundError, UnauthorizedError
from backend.api.schemas import AutonomousCycleRequest, PipelineRunRequest, SessionCreateRequest

router = APIRouter()
logger = logging.getLogger(__name__)

# Module-level state for cancellation and progress streaming
_cancel_events: dict[str, threading.Event] = {}
_progress_queues: dict[str, asyncio.Queue] = {}
_background_tasks: set[asyncio.Task] = set()


@router.post(
    "/run",
    summary="Trigger pipeline run",
    description="Start a new research pipeline run. Returns 202 with run_id immediately; the pipeline executes asynchronously.",
)
async def trigger_run(request: PipelineRunRequest):
    """Trigger a new pipeline run.

    Returns 202 with run_id immediately. The pipeline runs asynchronously;
    use /runs/{run_id}/progress to stream progress via SSE.

    Example request:
        {"domain": "AI/NLP", "max_gaps": 5, "generation_rounds": 2, "ideas_per_round": 3}

    Example response:
        {"run_id": "run_20260502_143000", "status": "running"}
    """
    from backend.pipeline.orchestrator import PipelineOrchestrator

    # Pre-generate run_id so SSE/cancel can work from t=0
    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")

    # Register progress queue and cancel event before starting
    _progress_queues[run_id] = asyncio.Queue()
    cancel_event = threading.Event()
    _cancel_events[run_id] = cancel_event

    def _stage_callback(stage_name: str, index: int, total: int, elapsed: float):
        if run_id in _progress_queues:
            progress_data = {
                "stage": stage_name,
                "index": index,
                "total": total,
                "elapsed": round(elapsed, 2),
            }
            with contextlib.suppress(Exception):
                _progress_queues[run_id].put_nowait(progress_data)
            # Also broadcast via WebSocket if enabled (BATCH-50)
            with contextlib.suppress(Exception):
                import asyncio as _asyncio
                from backend.api.ws import manager as ws_manager
                from backend.config import get_settings as _get_settings
                _settings = _get_settings()
                if _settings.websocket_enabled:
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None
                    if loop and loop.is_running():
                        loop.create_task(ws_manager.broadcast(f"pipeline:{run_id}", {
                            "type": "pipeline.progress",
                            "data": progress_data,
                        }))

    async def _run_pipeline():
        orchestrator = PipelineOrchestrator(stage_callback=_stage_callback, strategy=request.strategy)
        original_should_stop = orchestrator._should_stop

        def _should_stop_with_cancel():
            if cancel_event.is_set():
                return True
            return original_should_stop()

        orchestrator._should_stop = _should_stop_with_cancel

        try:
            await orchestrator.run(
                domain=request.domain,
                max_gaps=request.max_gaps,
                generation_rounds=request.generation_rounds,
                ideas_per_round=request.ideas_per_round,
                search_queries=request.search_queries,
                run_novelty=request.run_novelty,
                run_feasibility=request.run_feasibility,
                run_synthesis=request.run_synthesis,
                export_format=request.export_format,
                run_id=run_id,
                session_id=request.session_id,
            )
            # Fire completion webhook (BATCH-32)
            try:
                from backend.notifications import fire_webhook
                await fire_webhook("pipeline.completed", {
                    "run_id": run_id,
                    "domain": request.domain,
                    "status": "completed",
                })
            except Exception:
                logger.warning("Webhook failed for run %s", run_id, exc_info=True)
            # Fire notification (BATCH-49)
            try:
                from backend.notifications import create_notification
                await create_notification("pipeline.completed", "Pipeline run completed", f"Run {run_id} completed successfully")
            except Exception:
                logger.warning("Notification failed for run %s", run_id, exc_info=True)
        except Exception as e:
            logger.error("Pipeline run %s failed: %s", run_id, e)
            # Mark the DB record as failed if it exists and is still "running" (BATCH-55)
            try:
                from backend.db.database import get_session as _get_session_ctx
                from backend.db.models import PipelineRun as _PipelineRun
                from sqlalchemy import select as _sa_select
                with _get_session_ctx() as sess:
                    stmt = (
                        _sa_select(_PipelineRun)
                        .where(_PipelineRun.status == "running")
                        .order_by(_PipelineRun.id.desc())
                        .limit(1)
                    )
                    run_record = sess.execute(stmt).scalar_one_or_none()
                    if run_record:
                        run_record.status = "failed"
                        run_record.error_message = str(e)[:500]
                        run_record.completed_at = datetime.now(timezone.utc)
                        sess.commit()
                        logger.info("Marked run record %d as failed", run_record.id)
            except Exception as db_err:
                logger.warning("Failed to update run status in DB: %s", db_err)
            # Fire failure webhook (BATCH-32)
            try:
                from backend.notifications import fire_webhook
                await fire_webhook("pipeline.failed", {
                    "run_id": run_id,
                    "domain": request.domain,
                    "status": "failed",
                    "error": str(e),
                })
            except Exception:
                logger.warning("Webhook failed for run %s", run_id, exc_info=True)
            # Fire notification (BATCH-49)
            try:
                from backend.notifications import create_notification
                await create_notification("pipeline.failed", "Pipeline run failed", f"Run {run_id} failed")
            except Exception:
                logger.warning("Notification failed for run %s", run_id, exc_info=True)
        finally:
            # Signal completion to SSE listeners
            if run_id in _progress_queues:
                with contextlib.suppress(Exception):
                    _progress_queues[run_id].put_nowait({"done": True})
            _background_tasks.discard(asyncio.current_task())

    # Preflight validation (BATCH-172)
    from backend.pipeline.preflight import run_preflight
    preflight_report = await run_preflight(
        domain=request.domain,
        strategy=request.strategy,
    )
    if not preflight_report.can_proceed:
        from fastapi.responses import JSONResponse
        fatal_checks = [c for c in preflight_report.checks if c.severity.value == "fatal"]
        return JSONResponse(
            status_code=503,
            content={
                "error": "Pipeline preflight checks failed",
                "preflight": {
                    "can_proceed": False,
                    "fatal_count": preflight_report.fatal,
                    "warning_count": preflight_report.warnings,
                    "fatal_checks": [{"name": c.name, "message": c.message, "detail": c.detail} for c in fatal_checks],
                },
            },
        )

    task = asyncio.create_task(_run_pipeline())
    _background_tasks.add(task)

    return {"run_id": run_id, "status": "running", "preflight": {"can_proceed": True, "warnings": preflight_report.warnings}}


@router.get(
    "/runs",
    summary="List pipeline runs",
    description="List all pipeline runs with pagination and optional session_id filter.",
)
async def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session_id: str | None = Query(default=None, max_length=200),
):
    """List pipeline runs with pagination.

    Args:
        limit: Maximum number of runs to return (1-100).
        offset: Number of runs to skip.
        session_id: Optional filter to return only runs for a specific session.

    Returns:
        {"runs": [...], "total": 42}

    Example response:
        {"runs": [{"id": 1, "status": "completed", "domain": "AI/NLP", "current_stage": "done", "ideas_count": 5, "session_id": "sess-abc", "created_at": "...", "completed_at": "...", "error_message": null}], "total": 42}
    """
    from backend.db.crud import list_pipeline_runs, count_pipeline_runs
    from backend.db.database import get_session

    with get_session() as session:
        runs = list_pipeline_runs(session, limit=limit, offset=offset, session_id=session_id)
        total = count_pipeline_runs(session, session_id=session_id)
        return {
            "runs": [
                {
                    "id": r.id,
                    "status": r.status,
                    "domain": r.domain,
                    "current_stage": r.current_stage,
                    "ideas_count": len(r.ideas),
                    "session_id": r.session_id,
                    "created_at": str(r.created_at),
                    "completed_at": str(r.completed_at) if r.completed_at else None,
                    "error_message": r.error_message,
                }
                for r in runs
            ],
            "total": total,
        }


@router.post(
    "/resume/{run_id}",
    summary="Resume a pipeline run",
    description="Resume a failed pipeline from its last successful checkpoint. Reconstructs prior stage outputs then continues from the first unfinished stage.",
)
async def resume_pipeline(run_id: str):
    """Resume a failed pipeline from its last successful checkpoint.

    Reconstructs prior stage outputs from database + cross-stage context,
    then continues execution from the first unfinished stage.

    Args:
        run_id: The run identifier string (e.g. run_20260502_143000).

    Returns:
        {"status": "resumed", "run_id": "...", "ideas_count": 3, "gaps_count": 2, "proposals_count": 1}

    Example response:
        {"status": "resumed", "run_id": "run_20260502_143000", "ideas_count": 3, "gaps_count": 2, "proposals_count": 1}
    """
    from backend.pipeline.orchestrator import PipelineOrchestrator

    orchestrator = PipelineOrchestrator()
    result = await orchestrator.resume(run_id)
    if result is None:
        raise NotFoundError(f"No checkpoint found for run {run_id}")

    return {
        "status": "resumed",
        "run_id": run_id,
        "ideas_count": len(result.ideas),
        "gaps_count": len(result.gaps),
        "proposals_count": len(result.proposals),
    }


@router.get(
    "/runs/sessions",
    summary="List unique sessions",
    description="Return unique session_id values with run counts and latest run timestamps.",
)
async def list_sessions_for_runs():
    """List unique session IDs with aggregated run information.

    Returns:
        {"sessions": [{"session_id": "...", "run_count": 3, "latest_run_at": "..."}]}

    Example response:
        {"sessions": [{"session_id": "sess-abc", "run_count": 3, "latest_run_at": "2026-05-02 14:30:00+00:00"}]}
    """
    from backend.db.crud import list_session_ids
    from backend.db.database import get_session

    with get_session() as session:
        sessions = list_session_ids(session)
        return {"sessions": sessions}


# NOTE: Static paths (/runs/detail/) must be registered before dynamic
# ones (/runs/{run_id_str}/) to avoid path conflicts with FastAPI routing.


@router.get(
    "/runs/stale",
    summary="List stale pipeline runs",
    description="List pipeline runs stuck in 'running' status beyond the timeout.",
)
async def list_stale_runs(
    timeout_minutes: int = Query(default=30, ge=1, le=1440, description="Timeout in minutes"),
):
    """List stale running runs.

    Returns runs that have been in 'running' status longer than the
    specified timeout threshold.

    Args:
        timeout_minutes: Maximum minutes a run should be in 'running' state.

    Returns:
        {"stale_runs": [...], "count": N}

    Example response:
        {"stale_runs": [{"id": 1, "run_id": null, "domain": "AI/NLP", "created_at": "...", "age_minutes": 45.2}], "count": 1}
    """
    from datetime import timedelta
    from backend.db.database import get_session
    from backend.db.models import PipelineRun
    import sqlalchemy as sa

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

    with get_session() as session:
        runs = session.query(PipelineRun).filter(
            PipelineRun.status == "running",
            PipelineRun.created_at < cutoff,
        ).order_by(PipelineRun.created_at.asc()).limit(100).all()

        stale_runs = []
        now = datetime.now(timezone.utc)
        for run in runs:
            created = run.created_at.replace(tzinfo=timezone.utc) if run.created_at.tzinfo is None else run.created_at
            age = now - created
            stale_runs.append({
                "id": run.id,
                "run_id": getattr(run, 'run_id', None),
                "domain": run.domain,
                "created_at": str(run.created_at),
                "age_minutes": round(age.total_seconds() / 60, 1),
            })

        return {"stale_runs": stale_runs, "count": len(stale_runs)}


@router.get(
    "/runs/detail/{run_id}",
    summary="Get run details",
    description="Get full details for a pipeline run by its database ID, including config, stages, and ideas.",
)
async def get_run(run_id: int):
    """Get full run details by DB id.

    Args:
        run_id: The database primary key of the run.

    Returns:
        Full run object with config, stages_completed, and ideas list.

    Example response:
        {"id": 1, "status": "completed", "domain": "AI/NLP", "current_stage": "done", "config": {}, "stages_completed": ["generation", "novelty"], "ideas": [{"id": 1, "title": "...", "novelty_score": 0.8, "feasibility_score": 7.0, "overall_score": 0.75}], "created_at": "...", "completed_at": "...", "error_message": null}
    """
    from datetime import timedelta
    from backend.db.crud import get_pipeline_run
    from backend.db.database import get_session

    with get_session() as session:
        run = get_pipeline_run(session, run_id)
        if not run:
            raise NotFoundError("Run not found")

        # Compute stale flag (BATCH-177)
        timeout_minutes = 30  # Same default as watchdog
        stale = False
        if run.status == "running" and run.created_at:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
            created = run.created_at.replace(tzinfo=timezone.utc) if run.created_at.tzinfo is None else run.created_at
            stale = created < cutoff

        return {
            "id": run.id,
            "status": run.status,
            "domain": run.domain,
            "current_stage": run.current_stage,
            "config": json.loads(run.config_json) if run.config_json else {},
            "stages_completed": json.loads(run.stages_completed) if run.stages_completed else [],
            "ideas": [
                {
                    "id": i.id,
                    "title": i.title,
                    "novelty_score": i.novelty_score,
                    "feasibility_score": i.feasibility_score,
                    "overall_score": i.overall_score,
                    "parent_idea_ids": json.loads(i.parent_idea_ids) if i.parent_idea_ids else None,
                }
                for i in run.ideas
            ],
            "tree_data": json.loads(run.tree_data_json) if run.tree_data_json else None,
            "stage_report": json.loads(run.stage_report_json) if run.stage_report_json else [],
            "created_at": str(run.created_at),
            "completed_at": str(run.completed_at) if run.completed_at else None,
            "error_message": run.error_message,
            "stale": stale,
        }


@router.get(
    "/runs/{run_id}/ideas",
    summary="Get ideas for a pipeline run",
    description="Return all ideas generated by a specific pipeline run. Read-only endpoint.",
)
async def get_run_ideas(run_id: int):
    """Get all ideas for a pipeline run by its database ID.

    Args:
        run_id: The database primary key of the run.

    Returns:
        {"ideas": [...], "total": N}

    Example response:
        {"ideas": [{"id": 1, "title": "...", "problem_statement": "...", "proposed_method": "...", "expected_contributions": "...", "domain": "AI/NLP", "novelty_score": 0.8, "feasibility_score": 7.0, "overall_score": 0.75, "created_at": "..."}], "total": 3}
    """
    from backend.db.crud import get_ideas_for_run, count_ideas_for_run, get_pipeline_run
    from backend.db.database import get_session

    with get_session() as session:
        run = get_pipeline_run(session, run_id)
        if not run:
            raise NotFoundError("Run not found")
        ideas = get_ideas_for_run(session, run_id)
        total = count_ideas_for_run(session, run_id)
        return {
            "ideas": [
                {
                    "id": i.id,
                    "title": i.title,
                    "problem_statement": i.problem_statement,
                    "proposed_method": i.proposed_method,
                    "expected_contributions": i.expected_contributions,
                    "domain": i.domain,
                    "novelty_score": i.novelty_score,
                    "feasibility_score": i.feasibility_score,
                    "overall_score": i.overall_score,
                    "created_at": str(i.created_at),
                }
                for i in ideas
            ],
            "total": total,
        }


@router.delete(
    "/runs/{run_id_str}",
    summary="Cancel a pipeline run",
    description="Cancel a running pipeline by its run_id string.",
)
async def cancel_run(run_id_str: str):
    """Cancel a running pipeline by run_id.

    Args:
        run_id_str: The run identifier string (e.g. run_20260502_143000).

    Returns:
        {"status": "cancelling", "run_id": "..."}

    Example response:
        {"status": "cancelling", "run_id": "run_20260502_143000"}
    """
    event = _cancel_events.get(run_id_str)
    if not event:
        raise NotFoundError("Run not found or not cancellable")
    event.set()
    return {"status": "cancelling", "run_id": run_id_str}


@router.get(
    "/runs/{run_id_str}/progress",
    summary="Stream pipeline progress",
    description="Server-Sent Events (SSE) endpoint for streaming pipeline stage progress in real-time. Requires auth header (HB-01: no API keys in URLs).",
)
async def run_progress(run_id_str: str, request: Request):
    """SSE endpoint for pipeline progress.

    HB-01: Auth is validated via headers only — no API keys in URLs.
    The router-level dependency (verify_api_key) and JWT middleware
    handle auth, but we also validate explicitly for defence-in-depth.

    Args:
        run_id_str: The run identifier string.

    Returns:
        text/event-stream with JSON progress events.

    Example SSE events:
        data: {"stage": "generation", "index": 1, "total": 5, "elapsed": 2.3}
        data: {"done": true}
    """
    # HB-01: Defence-in-depth auth check — ensure credentials come via headers
    from backend.config import get_settings
    settings = get_settings()
    if settings.api_key:
        api_key = request.headers.get("X-API-Key", "")
        if not api_key or api_key != settings.api_key:
            raise UnauthorizedError(
                detail="SSE endpoint requires valid X-API-Key header",
                hint="Pass the API key via the X-API-Key header, not in the URL",
            )
    if settings.auth_enabled:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise UnauthorizedError(
                detail="SSE endpoint requires Authorization header",
                hint="Pass a Bearer token via the Authorization header",
            )

    queue = _progress_queues.get(run_id_str)
    if not queue:
        queue = asyncio.Queue()
        _progress_queues[run_id_str] = queue

    async def _stream():
        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(data)}\n\n"
                    if data.get("done"):
                        break
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'heartbeat': True})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _progress_queues.pop(run_id_str, None)

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.post(
    "/autonomous",
    summary="Start autonomous cycle",
    description="Start an autonomous research cycle that runs multiple pipeline iterations. Returns 202 immediately.",
)
async def start_autonomous_cycle(request: AutonomousCycleRequest):
    """Start an autonomous research cycle.

    Returns 202 immediately with a cycle_id. The cycle runs asynchronously.

    Example request:
        {"domain": "AI/NLP", "max_runs": 3}

    Example response:
        {"cycle_id": "auto_20260502_143000", "status": "running", "domain": "AI/NLP", "max_runs": 3}
    """
    from backend.pipeline.orchestrator import PipelineOrchestrator

    cycle_id = f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    _progress_queues[cycle_id] = asyncio.Queue()
    cancel_event = threading.Event()
    _cancel_events[cycle_id] = cancel_event

    def _stage_callback(stage_name: str, index: int, total: int, elapsed: float):
        if cycle_id in _progress_queues:
            with contextlib.suppress(Exception):
                _progress_queues[cycle_id].put_nowait(
                    {
                        "stage": stage_name,
                        "index": index,
                        "total": total,
                        "elapsed": round(elapsed, 2),
                    }
                )

    async def _run_cycle():
        orchestrator = PipelineOrchestrator(stage_callback=_stage_callback, strategy="deep_research")
        try:
            results = await orchestrator.autonomous_cycle(
                domain=request.domain,
                max_autonomous_runs=request.max_runs,
            )
            total_ideas = sum(len(r.ideas) for r in results)
            logger.info(
                "Autonomous cycle %s complete: %d runs, %d total ideas",
                cycle_id,
                len(results),
                total_ideas,
            )
            # Update history entry to completed
            for entry in _autonomous_history:
                if entry["cycle_id"] == cycle_id:
                    entry["status"] = "completed"
                    entry["runs"] = len(results)
                    break
        except Exception as e:
            logger.error("Autonomous cycle %s failed: %s", cycle_id, e)
        finally:
            if cycle_id in _progress_queues:
                with contextlib.suppress(Exception):
                    _progress_queues[cycle_id].put_nowait({"done": True})
            _background_tasks.discard(asyncio.current_task())

    task = asyncio.create_task(_run_cycle())
    _background_tasks.add(task)

    # Record in history
    _autonomous_history.append({
        "cycle_id": cycle_id,
        "domain": request.domain,
        "runs": 0,
        "status": "running",
    })

    return {
        "cycle_id": cycle_id,
        "status": "running",
        "domain": request.domain,
        "max_runs": request.max_runs,
    }


# ── Autonomous Cycle History ────────────────────────────────────────────

_autonomous_history: list[dict] = []


@router.post(
    "/autonomous/stop",
    summary="Stop autonomous cycle",
    description="Stop a running autonomous cycle. Requires cycle_id confirmation to prevent silent termination (HB-01).",
)
async def stop_autonomous_cycle(cycle_id: str = Query(..., max_length=200)):
    """Stop a running autonomous cycle.

    HB-01: Requires explicit cycle_id confirmation — no silent termination.

    Args:
        cycle_id: The autonomous cycle identifier to stop.

    Returns:
        {"status": "stopped", "cycle_id": "..."}

    Example response:
        {"status": "stopped", "cycle_id": "auto_20260502_143000"}
    """
    # Check cancel event for this cycle
    event = _cancel_events.get(cycle_id)
    if not event:
        raise NotFoundError(f"Cycle {cycle_id} not found or not running")

    event.set()

    # Update history entry
    for entry in _autonomous_history:
        if entry["cycle_id"] == cycle_id:
            entry["status"] = "stopped"
            break

    return {"status": "stopped", "cycle_id": cycle_id}


@router.get(
    "/autonomous/history",
    summary="Get autonomous cycle history",
    description="Return history of autonomous cycles with their statuses (running/completed/stopped).",
)
async def autonomous_history():
    """Get history of all autonomous cycles.

    Returns:
        {"cycles": [{"cycle_id": "...", "domain": "...", "runs": N, "status": "..."}]}

    Example response:
        {"cycles": [{"cycle_id": "auto_20260502_143000", "domain": "AI/NLP", "runs": 3, "status": "completed"}]}
    """
    return {"cycles": list(_autonomous_history)}


# ── Scheduler Control ──────────────────────────────────────────────────

_scheduler_orchestrator = None


def _get_orchestrator():
    global _scheduler_orchestrator
    if _scheduler_orchestrator is None:
        from backend.pipeline.orchestrator import PipelineOrchestrator
        _scheduler_orchestrator = PipelineOrchestrator()
    return _scheduler_orchestrator


@router.post(
    "/scheduler/start",
    summary="Start scheduler",
    description="Start the autonomous pipeline scheduler for periodic research cycles.",
)
async def scheduler_start():
    """Start the autonomous scheduler.

    Returns:
        {"status": "running"} or {"status": "not_configured", "message": "..."}

    Example response:
        {"status": "running", "interval_seconds": 3600}
    """
    orch = _get_orchestrator()
    result = await orch.start_scheduler()
    if result is None:
        return {"status": "not_configured", "message": "Scheduler not enabled in config"}
    return result


@router.post(
    "/scheduler/stop",
    summary="Stop scheduler",
    description="Stop the autonomous pipeline scheduler.",
)
async def scheduler_stop():
    """Stop the autonomous scheduler.

    Returns:
        {"status": "stopped"} or {"status": "not_configured"}

    Example response:
        {"status": "stopped"}
    """
    orch = _get_orchestrator()
    result = await orch.stop_scheduler()
    if result is None:
        return {"status": "not_configured"}
    return result


@router.get(
    "/scheduler/status",
    summary="Scheduler status",
    description="Get current status of the autonomous pipeline scheduler.",
)
async def scheduler_status():
    """Get current scheduler status.

    Returns:
        {"status": "running", ...} or {"status": "not_configured"}

    Example response:
        {"status": "running", "next_run": "2026-05-02T15:00:00Z"}
    """
    orch = _get_orchestrator()
    result = orch.scheduler_status()
    if result is None:
        return {"status": "not_configured"}
    return result


# ── Session Management ────────────────────────────────────────────────────


def _get_session_manager():
    orch = _get_orchestrator()
    mgr = getattr(orch, "_session_manager", None)
    if mgr is None:
        raise NotFoundError("Session management not enabled", hint="Enable sessions in platform configuration")
    return mgr


def _session_to_dict(session):
    return {
        "id": session.id,
        "name": session.name,
        "state": session.state.value,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "ended_at": session.ended_at,
        "run_count": session.run_count,
        "total_tokens": session.total_tokens,
        "total_cost": session.total_cost,
        "tags": session.tags,
        "metadata": session.metadata,
    }


@router.post(
    "/sessions",
    summary="Create session",
    description="Create a new pipeline session with budget constraints.",
)
async def create_session(request: SessionCreateRequest):
    """Create a new pipeline session with budget constraints.

    Example request:
        {"name": "My Session", "max_runs": 10, "max_cost_usd": 50.0, "tags": ["test"]}

    Example response:
        {"id": "sess_abc123", "name": "My Session", "state": "active", ...}
    """
    from backend.pipeline.session.models import SessionBudget

    mgr = _get_session_manager()
    budget = SessionBudget(
        max_runs=request.max_runs,
        max_total_cost_usd=request.max_cost_usd,
        max_total_tokens=request.max_tokens,
        max_duration_hours=request.max_duration_hours,
    )
    session = mgr.create(name=request.name, budget=budget, tags=request.tags, metadata=request.metadata)
    return _session_to_dict(session)


@router.get(
    "/sessions",
    summary="List sessions",
    description="List pipeline sessions with optional state filter and pagination.",
)
async def list_sessions(
    state: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """List pipeline sessions.

    Args:
        state: Optional session state filter (active, paused, ended).
        limit: Maximum number of sessions to return.

    Returns:
        {"sessions": [...]}

    Example response:
        {"sessions": [{"id": "sess_abc", "name": "My Session", "state": "active", "run_count": 3}]}
    """
    from backend.pipeline.session.models import SessionState

    mgr = _get_session_manager()
    s = SessionState(state) if state else None
    sessions = mgr.list(state=s, limit=limit)
    return {"sessions": [_session_to_dict(s) for s in sessions]}


@router.get(
    "/sessions/{session_id}",
    summary="Get session",
    description="Get details for a specific pipeline session.",
)
async def get_session(session_id: str):
    """Get details for a specific pipeline session.

    Args:
        session_id: The unique session identifier.

    Returns:
        Session object with id, name, state, budget usage, etc.

    Example response:
        {"id": "sess_abc123", "name": "My Session", "state": "active", "run_count": 3, "total_cost": 1.25}
    """
    mgr = _get_session_manager()
    session = mgr.get(session_id)
    if not session:
        raise NotFoundError("Session not found")
    return _session_to_dict(session)


@router.post(
    "/sessions/{session_id}/activate",
    summary="Activate session",
    description="Activate a paused or ended pipeline session.",
)
async def activate_session(session_id: str):
    """Activate a pipeline session.

    Args:
        session_id: The unique session identifier.

    Returns:
        Updated session object.

    Example response:
        {"id": "sess_abc", "name": "My Session", "state": "active"}
    """
    mgr = _get_session_manager()
    session = mgr.activate(session_id)
    return _session_to_dict(session)


@router.post(
    "/sessions/{session_id}/pause",
    summary="Pause session",
    description="Pause an active pipeline session.",
)
async def pause_session(session_id: str):
    """Pause a pipeline session.

    Args:
        session_id: The unique session identifier.

    Returns:
        Updated session object.

    Example response:
        {"id": "sess_abc", "name": "My Session", "state": "paused"}
    """
    mgr = _get_session_manager()
    session = mgr.pause(session_id)
    return _session_to_dict(session)


@router.post(
    "/sessions/{session_id}/resume",
    summary="Resume session",
    description="Resume a paused pipeline session.",
)
async def resume_session(session_id: str):
    """Resume a paused pipeline session.

    Args:
        session_id: The unique session identifier.

    Returns:
        Updated session object.

    Example response:
        {"id": "sess_abc", "name": "My Session", "state": "active"}
    """
    mgr = _get_session_manager()
    session = mgr.resume(session_id)
    return _session_to_dict(session)


@router.post(
    "/sessions/{session_id}/end",
    summary="End session",
    description="End a pipeline session permanently.",
)
async def end_session(session_id: str):
    """End a pipeline session permanently.

    Args:
        session_id: The unique session identifier.

    Returns:
        Updated session object.

    Example response:
        {"id": "sess_abc", "name": "My Session", "state": "ended"}
    """
    mgr = _get_session_manager()
    session = mgr.end(session_id)
    return _session_to_dict(session)


@router.get(
    "/sessions/{session_id}/budget",
    summary="Check session budget",
    description="Check remaining budget for a pipeline session.",
)
async def session_budget(session_id: str):
    """Check remaining budget for a pipeline session.

    Args:
        session_id: The unique session identifier.

    Returns:
        Budget usage and remaining amounts.

    Example response:
        {"used_cost_usd": 10.5, "remaining_cost_usd": 39.5, "used_tokens": 50000, "remaining_tokens": 450000}
    """
    mgr = _get_session_manager()
    return mgr.check_budget(session_id)


@router.post(
    "/watchdog",
    summary="Run pipeline watchdog",
    description="Detect and mark stale pipeline runs that have been in 'running' status beyond the timeout.",
)
async def run_watchdog(
    timeout_minutes: int = Query(default=30, ge=1, le=1440, description="Timeout in minutes"),
):
    """Detect and mark stale pipeline runs.

    Scans for pipeline runs stuck in 'running' status for longer than the
    specified timeout and marks them as 'failed'.

    Args:
        timeout_minutes: Maximum minutes a run should be in 'running' state.

    Returns:
        Count of runs marked as failed.

    Example response:
        {"checked": true, "stale_found": 3, "marked_failed": 3, "timeout_minutes": 30}
    """
    from datetime import timedelta
    from backend.pipeline.execution.watchdog import PipelineWatchdog
    from backend.pipeline.persistence import PipelinePersistence

    persistence = PipelinePersistence()
    watchdog = PipelineWatchdog(persistence, timeout=timedelta(minutes=timeout_minutes))
    marked = await watchdog.check_and_mark_stale_runs()

    return {
        "checked": True,
        "stale_found": marked,
        "marked_failed": marked,
        "timeout_minutes": timeout_minutes,
    }


@router.get("/runs/stats", response_model=dict)
async def run_stats():
    """Get aggregate statistics across all pipeline runs.

    Returns counts by status, average duration, total ideas/gaps generated.
    """
    from backend.pipeline.persistence import PipelinePersistence

    persistence = PipelinePersistence()
    try:
        runs = persistence.list_runs(limit=1000)

        total = len(runs)
        by_status: dict[str, int] = {}
        total_duration = 0.0
        total_ideas = 0
        total_gaps = 0

        for run in runs:
            status = getattr(run, 'status', 'unknown')
            by_status[status] = by_status.get(status, 0) + 1
            duration = getattr(run, 'duration_seconds', 0) or 0
            total_duration += duration
            total_ideas += getattr(run, 'idea_count', 0) or 0
            total_gaps += getattr(run, 'gap_count', 0) or 0

        return {
            "total_runs": total,
            "by_status": by_status,
            "avg_duration_s": round(total_duration / total, 1) if total else 0,
            "total_ideas": total_ideas,
            "total_gaps": total_gaps,
        }
    except Exception as e:
        return {
            "total_runs": 0,
            "by_status": {},
            "avg_duration_s": 0,
            "total_ideas": 0,
            "total_gaps": 0,
            "error": str(e),
        }


@router.get(
    "/runs/{run_id}/journal",
    summary="Get pipeline run journal",
    description="Retrieve the research journal (notes + README) for a completed run (B162).",
)
async def get_run_journal(run_id: str):
    """Get the journal for a pipeline run.

    Returns the notes.md and README.md contents generated during the run.
    """
    from pathlib import Path

    journal_dir = Path(f"./data/runs/{run_id}")
    if not journal_dir.exists():
        # Try with run_ prefix
        journal_dir = Path(f"./data/runs/run_{run_id}")

    result = {"run_id": run_id, "notes": None, "readme": None}

    notes_path = journal_dir / "notes.md"
    readme_path = journal_dir / "README.md"

    if notes_path.exists():
        result["notes"] = notes_path.read_text(encoding="utf-8", errors="replace")
    if readme_path.exists():
        result["readme"] = readme_path.read_text(encoding="utf-8", errors="replace")

    if result["notes"] is None and result["readme"] is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={"error": "No journal found for this run", "run_id": run_id},
        )

    return result


@router.get(
    "/plan",
    summary="Get execution plan",
    description="Preview the execution plan for a given strategy and domain (B164).",
)
async def get_execution_plan(
    strategy: str = "deep_research",
    domain: str = "",
):
    """Get a preview of the pipeline execution plan."""
    from backend.pipeline.planning.agent import PlanningAgent

    agent = PlanningAgent()

    # Determine disabled stages based on strategy
    disabled = []
    if strategy == "fast_scan":
        disabled = ["adversarial_review", "paper_synthesis", "citation_audit",
                     "gap_reflection", "idea_reflection"]

    plan = agent.plan(domain=domain, strategy=strategy, disabled_stages=disabled)
    return plan.to_dict()


@router.get(
    "/runs/{run_id}/citation-graph",
    summary="Get citation graph data",
    description="Get citation graph data for a pipeline run (B170).",
)
async def get_citation_graph(run_id: str):
    """Get citation graph data for visualization.

    Returns nodes (papers) and edges (citations) for the run.
    """
    try:
        from backend.db.database import get_session
        from backend.db.models import PipelineRun

        with next(get_session()) as db:
            run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
            if not run:
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=404, content={"error": "Run not found"})

        # Build graph from run results
        papers = run.result.get("papers", []) if isinstance(run.result, dict) else []
        ideas = run.result.get("ideas", []) if isinstance(run.result, dict) else []

        nodes = []
        edges = []
        seen = set()

        for p in papers[:50]:
            pid = p.get("id", p.get("title", ""))[:20]
            if pid not in seen:
                seen.add(pid)
                nodes.append({
                    "id": pid,
                    "label": p.get("title", "Unknown")[:60],
                    "type": "paper",
                    "year": p.get("year"),
                    "source": p.get("source", ""),
                })

        for idea in ideas[:20]:
            iid = f"idea_{idea.get('id', len(nodes))}"
            if iid not in seen:
                seen.add(iid)
                nodes.append({
                    "id": iid,
                    "label": idea.get("title", "Idea")[:60],
                    "type": "idea",
                    "score": idea.get("overall_score", 0),
                })

        return {"run_id": run_id, "nodes": nodes, "edges": edges}
    except Exception as e:
        return {"run_id": run_id, "nodes": [], "edges": [], "error": str(e)}
