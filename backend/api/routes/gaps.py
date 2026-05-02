"""Gaps API routes."""

from fastapi import APIRouter, Query

from backend.api.errors import NotFoundError

router = APIRouter()


@router.get(
    "/",
    summary="List research gaps",
    description="List research gaps from a pipeline run. Uses the latest completed run if run_id is omitted.",
)
async def list_gaps(
    run_id: int | None = Query(default=None, help="Pipeline run ID (latest if omitted)"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """List research gaps from a pipeline run.

    Args:
        run_id: Optional pipeline run ID. Defaults to the latest completed run.
        limit: Maximum number of gaps to return.

    Returns:
        {"gaps": [...], "total": 5, "run_id": 1}

    Example response:
        {"gaps": [{"id": 1, "title": "Limited cross-domain evaluation", "description": "...", "gap_type": "methodological", "confidence": 0.85, "potential_impact": "high"}], "total": 5, "run_id": 1}
    """
    from sqlalchemy import select

    from backend.db.crud import count_gaps_by_run, count_ideas_for_gap, list_gaps_by_run
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
                    "idea_count": count_ideas_for_gap(session, g.title),
                }
                for g in gaps
            ],
            "total": total,
            "run_id": target_run,
        }


@router.get(
    "/{gap_id}",
    summary="Get gap details",
    description="Get full details for a specific research gap by its ID.",
)
async def get_gap(gap_id: int):
    """Get gap details.

    Args:
        gap_id: The database primary key of the gap.

    Returns:
        {"gap": {...}}

    Example response:
        {"gap": {"id": 1, "title": "Limited cross-domain evaluation", "description": "...", "gap_type": "methodological", "confidence": 0.85, "potential_impact": "high", "pipeline_run_id": 1, "created_at": "2026-05-02T14:30:00"}}
    """
    from backend.db.crud import count_ideas_for_gap, get_gap as db_get_gap
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
                "idea_count": count_ideas_for_gap(session, gap.title),
                "pipeline_run_id": gap.pipeline_run_id,
                "created_at": str(gap.created_at),
            },
        }
