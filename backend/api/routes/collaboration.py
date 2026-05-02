"""Collaboration API routes — comments + sharing (BATCH-34)."""

import json
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.api.errors import NotFoundError

router = APIRouter()


class CommentCreateRequest(BaseModel):
    author: str = Field(default="anonymous", max_length=128)
    content: str = Field(min_length=1, max_length=5000)
    parent_id: int | None = Field(default=None, description="Parent comment ID for replies")


class ShareCreateRequest(BaseModel):
    pass  # No fields needed — just triggers token generation


# ── Comments ───────────────────────────────────────────────────────


@router.post(
    "/{idea_id}/comments",
    summary="Add a comment",
    description="Add a comment (or reply) to a research idea.",
)
async def add_comment(idea_id: int, request: CommentCreateRequest):
    """Add a comment to an idea.

    Args:
        idea_id: The database primary key of the idea.
        request: Comment with author, content, and optional parent_id for replies.

    Returns:
        {"id": 1, "idea_id": 1, "author": "alice", "content": "...", "parent_id": null, "created_at": "..."}
    """
    from backend.db.crud import get_idea as db_get_idea
    from backend.db.database import get_session
    from backend.db.models import Comment

    with get_session() as session:
        idea = db_get_idea(session, idea_id)
        if not idea:
            raise NotFoundError("Idea not found")

        comment = Comment(
            idea_id=idea_id,
            author=request.author,
            content=request.content,
            parent_id=request.parent_id,
        )
        session.add(comment)
        session.commit()
        session.refresh(comment)

        return {
            "id": comment.id,
            "idea_id": comment.idea_id,
            "author": comment.author,
            "content": comment.content,
            "parent_id": comment.parent_id,
            "created_at": str(comment.created_at),
        }


@router.get(
    "/{idea_id}/comments",
    summary="List comments",
    description="List all comments for a research idea in chronological order.",
)
async def list_comments(idea_id: int):
    """List comments for an idea.

    Args:
        idea_id: The database primary key of the idea.

    Returns:
        {"comments": [...], "total": 5}
    """
    from backend.db.database import get_session
    from backend.db.models import Comment
    from sqlalchemy import select, func

    with get_session() as session:
        comments = (
            session.execute(
                select(Comment)
                .where(Comment.idea_id == idea_id)
                .order_by(Comment.created_at.asc())
            )
            .scalars()
            .all()
        )
        total = session.execute(
            select(func.count()).select_from(Comment).where(Comment.idea_id == idea_id)
        ).scalar_one()

        return {
            "comments": [
                {
                    "id": c.id,
                    "idea_id": c.idea_id,
                    "author": c.author,
                    "content": c.content,
                    "parent_id": c.parent_id,
                    "created_at": str(c.created_at),
                }
                for c in comments
            ],
            "total": total,
        }


# ── Sharing ────────────────────────────────────────────────────────


@router.post(
    "/{idea_id}/share",
    summary="Create share link",
    description="Generate a unique shareable link token for a research idea.",
)
async def create_share_link(idea_id: int):
    """Create a share link for an idea.

    Args:
        idea_id: The database primary key of the idea.

    Returns:
        {"id": 1, "idea_id": 1, "token": "abc123...", "share_url": "/shared/abc123...", "created_at": "..."}
    """
    from backend.db.crud import get_idea as db_get_idea
    from backend.db.database import get_session
    from backend.db.models import SharedIdea

    with get_session() as session:
        idea = db_get_idea(session, idea_id)
        if not idea:
            raise NotFoundError("Idea not found")

        token = secrets.token_urlsafe(32)
        shared = SharedIdea(idea_id=idea_id, token=token)
        session.add(shared)
        session.commit()
        session.refresh(shared)

        return {
            "id": shared.id,
            "idea_id": shared.idea_id,
            "token": shared.token,
            "share_url": f"/shared/{shared.token}",
            "created_at": str(shared.created_at),
        }


# ── Shared Idea (public, mounted at /api/v1/shared) ───────────────


@router.get(
    "/shared/{token}",
    summary="Get shared idea",
    description="Retrieve a shared idea by its unique share token (no auth required).",
)
async def get_shared_idea(token: str):
    """Retrieve a shared idea by token.

    Args:
        token: The unique share token.

    Returns:
        {"idea": {...}} with full idea details (read-only, no proposal).
    """
    from backend.db.database import get_session
    from backend.db.models import SharedIdea, Idea
    from sqlalchemy import select

    with get_session() as session:
        shared = session.execute(
            select(SharedIdea).where(SharedIdea.token == token)
        ).scalar_one_or_none()

        if not shared:
            raise NotFoundError("Shared idea not found")

        idea = session.get(Idea, shared.idea_id)
        if not idea:
            raise NotFoundError("Idea not found")

        return {
            "idea": {
                "id": idea.id,
                "title": idea.title,
                "problem_statement": idea.problem_statement,
                "proposed_method": idea.proposed_method,
                "expected_contributions": idea.expected_contributions,
                "domain": idea.domain,
                "novelty_score": idea.novelty_score,
                "feasibility_score": idea.feasibility_score,
                "overall_score": idea.overall_score,
                "source_gap_ids": json.loads(idea.source_gap_ids) if idea.source_gap_ids else None,
                "created_at": str(idea.created_at),
            },
        }
