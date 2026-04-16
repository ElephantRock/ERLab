"""Gaps API routes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_gaps(
    domain: str | None = None,
    min_confidence: float = 0.0,
    limit: int = 20,
):
    """List research gaps."""
    return {"gaps": [], "total": 0, "message": "Requires DB integration (Gap 12)"}


@router.get("/{gap_id}")
async def get_gap(gap_id: str):
    """Get gap details."""
    return {"gap": None, "message": "Requires DB integration (Gap 12)"}
