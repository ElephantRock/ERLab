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


@router.post("/run")
async def trigger_run(request: PipelineRunRequest):
    """Trigger a new pipeline run. Returns 202 with run_id immediately."""
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


@router.get("/runs")
async def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List pipeline runs."""
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


# NOTE: Static paths (/runs/detail/) must be registered before dynamic
# ones (/runs/{run_id_str}/) to avoid path conflicts with FastAPI routing.


@router.get("/runs/detail/{run_id}")
async def get_run(run_id: int):
    """Get full run details by DB id."""
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


@router.delete("/runs/{run_id_str}")
async def cancel_run(run_id_str: str):
    """Cancel a running pipeline by run_id string."""
    event = _cancel_events.get(run_id_str)
    if not event:
        raise NotFoundError("Run not found or not cancellable")
    event.set()
    return {"status": "cancelling", "run_id": run_id_str}


@router.get("/runs/{run_id_str}/progress")
async def run_progress(run_id_str: str):
    """SSE endpoint for pipeline progress."""
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


@router.post("/autonomous")
async def start_autonomous_cycle(request: AutonomousCycleRequest):
    """Start an autonomous research cycle. Returns 202 immediately."""
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


@router.post("/scheduler/start")
async def scheduler_start():
    """Start the autonomous scheduler."""
    orch = _get_orchestrator()
    result = await orch.start_scheduler()
    if result is None:
        return {"status": "not_configured", "message": "Scheduler not enabled in config"}
    return result


@router.post("/scheduler/stop")
async def scheduler_stop():
    """Stop the autonomous scheduler."""
    orch = _get_orchestrator()
    result = await orch.stop_scheduler()
    if result is None:
        return {"status": "not_configured"}
    return result


@router.get("/scheduler/status")
async def scheduler_status():
    """Get current scheduler status."""
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
        raise NotFoundError("Session management not enabled")
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


@router.post("/sessions")
async def create_session(request: SessionCreateRequest):
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


@router.get("/sessions")
async def list_sessions(
    state: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    from backend.pipeline.session.models import SessionState

    mgr = _get_session_manager()
    s = SessionState(state) if state else None
    sessions = mgr.list(state=s, limit=limit)
    return {"sessions": [_session_to_dict(s) for s in sessions]}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    mgr = _get_session_manager()
    session = mgr.get(session_id)
    if not session:
        raise NotFoundError("Session not found")
    return _session_to_dict(session)


@router.post("/sessions/{session_id}/activate")
async def activate_session(session_id: str):
    mgr = _get_session_manager()
    session = mgr.activate(session_id)
    return _session_to_dict(session)


@router.post("/sessions/{session_id}/pause")
async def pause_session(session_id: str):
    mgr = _get_session_manager()
    session = mgr.pause(session_id)
    return _session_to_dict(session)


@router.post("/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    mgr = _get_session_manager()
    session = mgr.resume(session_id)
    return _session_to_dict(session)


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: str):
    mgr = _get_session_manager()
    session = mgr.end(session_id)
    return _session_to_dict(session)


@router.get("/sessions/{session_id}/budget")
async def session_budget(session_id: str):
    mgr = _get_session_manager()
    return mgr.check_budget(session_id)
