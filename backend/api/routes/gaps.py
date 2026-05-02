"""Gaps API routes."""

import json

from fastapi import APIRouter, Query

from backend.api.errors import NotFoundError

router = APIRouter()

# AR-01 / AR-02 whitelists
SORT_BY_WHITELIST = {"confidence", "date", "type"}
GAP_TYPE_WHITELIST = {"methodological", "empirical", "theoretical", "cross-domain"}


def _build_truth(gap) -> dict | None:
    """Build truth object from a ResearchGapDB row (BATCH-38+)."""
    return {
        "frequency": gap.truth_frequency,
        "confidence": gap.truth_confidence,
        "evidence_count": gap.truth_evidence_count,
    }


def _build_related_clusters(gap) -> list[int] | None:
    """Parse related_clusters JSON text into list[int] or None."""
    if gap.related_clusters is None:
        return None
    try:
        parsed = json.loads(gap.related_clusters)
        if isinstance(parsed, list):
            return [int(c) for c in parsed]
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return None


@router.get(
    "/",
    summary="List research gaps",
    description="List research gaps from a pipeline run. Uses the latest completed run if run_id is omitted.",
)
async def list_gaps(
    run_id: int | None = Query(default=None, description="Pipeline run ID (latest if omitted)"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, description="Case-insensitive substring match on title and description"),
    gap_type: str | None = Query(default=None, description="Filter by gap type: methodological, empirical, theoretical, cross-domain"),
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0, description="Minimum confidence threshold (0.0-1.0)"),
    sort_by: str = Query(default="confidence", description="Sort column: confidence, date, type"),
    sort_order: str = Query(default="desc", description="Sort direction: asc or desc"),
):
    """List research gaps from a pipeline run with search, filter, and sort.

    Args:
        run_id: Optional pipeline run ID. Defaults to the latest completed run.
        limit: Maximum number of gaps to return.
        offset: Pagination offset.
        search: Case-insensitive substring match on title and description.
        gap_type: Exact match filter (validated against whitelist).
        min_confidence: Minimum confidence threshold.
        sort_by: Column to sort by (validated against whitelist — AR-01).
        sort_order: Sort direction (asc/desc).

    Returns:
        {"gaps": [...], "total": 5, "run_id": 1}

    Example response:
        {"gaps": [{"id": 1, "title": "Limited cross-domain evaluation", "description": "...", "gap_type": "methodological", "confidence": 0.85, "potential_impact": "high", "truth": {"frequency": 0.5, "confidence": 0.5, "evidence_count": 0}, "related_clusters": null}], "total": 5, "run_id": 1}
    """
    from sqlalchemy import select

    from backend.db.crud import count_ideas_for_gap, search_gaps, count_search_gaps
    from backend.db.database import get_session
    from backend.db.models import PipelineRun

    # AR-01: validate sort_by against whitelist
    validated_sort = sort_by if sort_by in SORT_BY_WHITELIST else "confidence"

    # AR-02: validate gap_type against whitelist
    validated_type = gap_type if gap_type in GAP_TYPE_WHITELIST else None

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

        total = count_search_gaps(
            session,
            run_id=target_run,
            search=search,
            gap_type=validated_type,
            min_confidence=min_confidence,
        )
        gaps = search_gaps(
            session,
            run_id=target_run,
            search=search,
            gap_type=validated_type,
            min_confidence=min_confidence,
            sort_by=validated_sort,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )
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
                    "truth": _build_truth(g),
                    "related_clusters": _build_related_clusters(g),
                    "status": getattr(g, "status", "identified"),
                    "user_rating": getattr(g, "user_rating", None),
                    "user_notes": getattr(g, "user_notes", None),
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
                "truth": _build_truth(gap),
                "related_clusters": _build_related_clusters(gap),
                "status": getattr(gap, "status", "identified"),
                "user_rating": getattr(gap, "user_rating", None),
                "user_notes": getattr(gap, "user_notes", None),
            },
        }


# ── BATCH-41: Feedback & Lifecycle endpoints ──────────────────────

VALID_STATUSES = {"identified", "investigating", "addressed"}


@router.post(
    "/{gap_id}/feedback",
    summary="Submit gap feedback",
    description="Rate a gap 1-5 stars with optional notes (BATCH-41).",
)
async def submit_feedback(gap_id: int, rating: int = Query(..., ge=1, le=5, description="Star rating 1-5"), notes: str | None = Query(default=None, max_length=2000)):
    from backend.db.crud import update_gap_feedback
    from backend.db.database import get_session

    with get_session() as session:
        gap = update_gap_feedback(session, gap_id, rating, notes)
        if not gap:
            raise NotFoundError("Gap not found")
        return {
            "gap": {
                "id": gap.id,
                "user_rating": gap.user_rating,
                "user_notes": gap.user_notes,
            },
        }


@router.patch(
    "/{gap_id}/status",
    summary="Update gap lifecycle status",
    description="Transition gap status forward: identified → investigating → addressed (BATCH-41).",
)
async def update_status(gap_id: int, status: str = Query(..., description="New status: identified, investigating, addressed")):
    from backend.db.crud import update_gap_status
    from backend.db.database import get_session
    from fastapi import HTTPException

    if status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}")

    with get_session() as session:
        gap = update_gap_status(session, gap_id, status)
        if not gap:
            raise HTTPException(status_code=422, detail=f"Invalid transition. Forward-only: identified → investigating → addressed")
        return {
            "gap": {
                "id": gap.id,
                "status": gap.status,
            },
        }
