"""Pipeline API routes."""

import asyncio
import contextlib
import json
import logging
import threading
from datetime import datetime

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from backend.api.errors import NotFoundError
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
            with contextlib.suppress(Exception):
                _progress_queues[run_id].put_nowait(
                    {
                        "stage": stage_name,
                        "index": index,
                        "total": total,
                        "elapsed": round(elapsed, 2),
                    }
                )

    async def _run_pipeline():
        orchestrator = PipelineOrchestrator(stage_callback=_stage_callback)
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
        except Exception as e:
            logger.error("Pipeline run %s failed: %s", run_id, e)
        finally:
            # Signal completion to SSE listeners
            if run_id in _progress_queues:
                with contextlib.suppress(Exception):
                    _progress_queues[run_id].put_nowait({"done": True})
            _background_tasks.discard(asyncio.current_task())

    task = asyncio.create_task(_run_pipeline())
    _background_tasks.add(task)

    return {"run_id": run_id, "status": "running"}


@router.get(
    "/runs",
    summary="List pipeline runs",
    description="List all pipeline runs with pagination support.",
)
async def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List pipeline runs with pagination.

    Args:
        limit: Maximum number of runs to return (1-100).
        offset: Number of runs to skip.

    Returns:
        {"runs": [...], "total": 42}

    Example response:
        {"runs": [{"id": 1, "status": "completed", "domain": "AI/NLP", "current_stage": "done", "ideas_count": 5, "created_at": "...", "completed_at": "...", "error_message": null}], "total": 42}
    """
    from backend.db.crud import list_pipeline_runs, count_pipeline_runs
    from backend.db.database import get_session

    with get_session() as session:
        runs = list_pipeline_runs(session, limit=limit, offset=offset)
        total = count_pipeline_runs(session)
        return {
            "runs": [
                {
                    "id": r.id,
                    "status": r.status,
                    "domain": r.domain,
                    "current_stage": r.current_stage,
                    "ideas_count": len(r.ideas),
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


# NOTE: Static paths (/runs/detail/) must be registered before dynamic
# ones (/runs/{run_id_str}/) to avoid path conflicts with FastAPI routing.


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
    from backend.db.crud import get_pipeline_run
    from backend.db.database import get_session

    with get_session() as session:
        run = get_pipeline_run(session, run_id)
        if not run:
            raise NotFoundError("Run not found")
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
                }
                for i in run.ideas
            ],
            "created_at": str(run.created_at),
            "completed_at": str(run.completed_at) if run.completed_at else None,
            "error_message": run.error_message,
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
    description="Server-Sent Events (SSE) endpoint for streaming pipeline stage progress in real-time.",
)
async def run_progress(run_id_str: str):
    """SSE endpoint for pipeline progress.

    Args:
        run_id_str: The run identifier string.

    Returns:
        text/event-stream with JSON progress events.

    Example SSE events:
        data: {"stage": "generation", "index": 1, "total": 5, "elapsed": 2.3}
        data: {"done": true}
    """
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
        orchestrator = PipelineOrchestrator(stage_callback=_stage_callback)
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
        except Exception as e:
            logger.error("Autonomous cycle %s failed: %s", cycle_id, e)
        finally:
            if cycle_id in _progress_queues:
                with contextlib.suppress(Exception):
                    _progress_queues[cycle_id].put_nowait({"done": True})
            _background_tasks.discard(asyncio.current_task())

    task = asyncio.create_task(_run_cycle())
    _background_tasks.add(task)

    return {
        "cycle_id": cycle_id,
        "status": "running",
        "domain": request.domain,
        "max_runs": request.max_runs,
    }


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
