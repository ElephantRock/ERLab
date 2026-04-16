"""Ideas API routes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_ideas(
    domain: str | None = None,
    min_score: float = 0.0,
    limit: int = 20,
):
    """List research ideas with optional filters."""
    # Placeholder — requires DB integration
    return {"ideas": [], "total": 0, "message": "Requires DB integration (Gap 12)"}


@router.get("/{idea_id}")
async def get_idea(idea_id: str):
    """Get a specific idea with novelty and feasibility reports."""
    return {"idea": None, "message": "Requires DB integration (Gap 12)"}
