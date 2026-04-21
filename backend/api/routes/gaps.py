"""Gaps API routes."""

from fastapi import APIRouter, Query

from backend.api.errors import NotFoundError

router = APIRouter()


@router.get("/")
async def list_gaps(
    run_id: int | None = Query(default=None, help="Pipeline run ID (latest if omitted)"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """List research gaps from a pipeline run (latest if run_id omitted)."""
    from sqlalchemy import select

    from backend.db.crud import count_gaps_by_run, list_gaps_by_run
    from backend.db.database import get_session
    from backend.db.models import PipelineRun

    with get_session() as session:
        target_run = run_id
        if target_run is None:
            latest = (
                session.execute(
                    select(PipelineRun)
                    .where(PipelineRun.status == "completed")
                    .order_by(PipelineRun.id.desc())
                    .limit(1)
                )
                .scalar_one_or_none()
            )
            if not latest:
                return {"gaps": [], "total": 0}
            target_run = latest.id

        total = count_gaps_by_run(session, target_run)
        gaps = list_gaps_by_run(session, target_run)[:limit]
        return {
            "gaps": [
                {
                    "id": g.id,
                    "title": g.title,
                    "description": g.description,
                    "gap_type": g.gap_type,
                    "confidence": g.confidence,
                    "potential_impact": g.potential_impact,
                }
                for g in gaps
            ],
            "total": total,
            "run_id": target_run,
        }


@router.get("/{gap_id}")
async def get_gap(gap_id: int):
    """Get gap details."""
    from backend.db.crud import get_gap as db_get_gap
    from backend.db.database import get_session

    with get_session() as session:
        gap = db_get_gap(session, gap_id)
        if not gap:
            raise NotFoundError("Gap not found")
        return {
            "gap": {
                "id": gap.id,
                "title": gap.title,
                "description": gap.description,
                "gap_type": gap.gap_type,
                "confidence": gap.confidence,
                "potential_impact": gap.potential_impact,
                "pipeline_run_id": gap.pipeline_run_id,
                "created_at": str(gap.created_at),
            },
        }
