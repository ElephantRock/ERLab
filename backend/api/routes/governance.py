"""Governance approval API routes.

Two route groups:
1. Pipeline gate approvals (ephemeral, in-memory ApprovalManager)
2. Idea-scoped governance decisions (persistent, append-only)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from typing import Literal

from backend.api.errors import NotFoundError, ServiceUnavailableError
from backend.api.auth import get_current_user, TokenData
from backend.db.database import get_session
from backend.db.models import GovernanceDecision, Comment, Proposal, ProposalSectionRevision

router = APIRouter()

# Router for idea-scoped governance routes (mounted at /api/v1/ideas)
idea_governance_router = APIRouter()


class DenyRequest(BaseModel):
    amendment: str | None = None


# Module-level reference to the approval manager, set during app startup.
_approval_manager = None


def set_approval_manager(manager) -> None:
    global _approval_manager
    _approval_manager = manager


def _get_manager():
    if _approval_manager is None:
        raise ServiceUnavailableError("Governance not initialized", hint="Ensure governance is enabled in platform configuration")
    return _approval_manager


@router.get(
    "/pending",
    summary="List pending approvals",
    description="List all pending governance approvals awaiting human decision.",
)
async def list_pending_approvals():
    """List all pending governance approvals.

    Returns:
        {"pending": [...]}

    Example response:
        {"pending": [{"id": "gap_001", "type": "gap_approval", "summary": "..."}]}
    """
    manager = _get_manager()
    return {"pending": manager.get_pending()}


@router.post(
    "/{decision_id}/approve",
    summary="Approve a decision",
    description="Approve a pending governance decision by its ID.",
)
async def approve_decision(decision_id: str):
    """Approve a pending governance decision.

    Args:
        decision_id: The unique identifier of the pending decision.

    Returns:
        {"status": "approved", "decision_id": "..."}

    Example response:
        {"status": "approved", "decision_id": "gap_001"}
    """
    manager = _get_manager()
    if not manager.approve(decision_id):
        raise NotFoundError(f"No pending approval '{decision_id}'")
    return {"status": "approved", "decision_id": decision_id}


@router.post(
    "/{decision_id}/deny",
    summary="Deny a decision",
    description="Deny a pending governance decision with an optional amendment.",
)
async def deny_decision(decision_id: str, body: DenyRequest | None = None):
    """Deny a pending governance decision.

    Args:
        decision_id: The unique identifier of the pending decision.
        body: Optional denial body with amendment text.

    Returns:
        {"status": "denied", "decision_id": "...", "amendment": "..."}

    Example request:
        {"amendment": "Please refine the methodology section"}

    Example response:
        {"status": "denied", "decision_id": "gap_001", "amendment": "Please refine the methodology section"}
    """
    manager = _get_manager()
    amendment = body.amendment if body else None
    if not manager.deny(decision_id, amendment=amendment):
        raise NotFoundError(f"No pending approval '{decision_id}'")
    return {"status": "denied", "decision_id": decision_id, "amendment": amendment}


# ── Idea-scoped governance decisions (persistent) ───────────────

VALID_DECISIONS = Literal["approved", "denied", "needs_changes"]


class GovernanceDecisionRequest(BaseModel):
    decision: VALID_DECISIONS = Field(description="One of: approved, denied, needs_changes")
    note: str | None = Field(default=None, max_length=5000, description="Optional reviewer note")
    reviewer: str | None = Field(default=None, max_length=128, description="Reviewer identity (defaults to auth user or anonymous)")


@idea_governance_router.post(
    "/{idea_id}/governance/decision",
    summary="Create governance decision",
    description="Record an append-only governance decision for an idea.",
)
async def create_decision(
    idea_id: int,
    request: GovernanceDecisionRequest,
    user: TokenData = Depends(get_current_user),
):
    """Create a governance decision for an idea.

    Decisions are append-only — creating a new decision does not modify
    prior decisions. The timeline reflects the full history.

    Args:
        idea_id: The idea ID.
        request: Decision, optional note, optional reviewer override.

    Returns:
        Created decision object.
    """
    from backend.db.crud import get_idea as db_get_idea

    with get_session() as session:
        idea = db_get_idea(session, idea_id)
        if not idea:
            raise NotFoundError("Idea not found")

        reviewer = request.reviewer or user.username or "anonymous"

        decision = GovernanceDecision(
            idea_id=idea_id,
            decision=request.decision,
            reviewer=reviewer,
            note=request.note,
        )
        session.add(decision)
        session.commit()
        session.refresh(decision)

        return {
            "id": decision.id,
            "idea_id": decision.idea_id,
            "decision": decision.decision,
            "reviewer": decision.reviewer,
            "note": decision.note,
            "created_at": str(decision.created_at),
        }


@idea_governance_router.get(
    "/{idea_id}/governance/decisions",
    summary="List governance decisions",
    description="List all governance decisions for an idea in chronological order.",
)
async def list_decisions(idea_id: int):
    """List governance decisions for an idea.

    Args:
        idea_id: The idea ID.

    Returns:
        {"decisions": [...], "total": N}
    """
    with get_session() as session:
        decisions = (
            session.execute(
                select(GovernanceDecision)
                .where(GovernanceDecision.idea_id == idea_id)
                .order_by(GovernanceDecision.created_at.desc())
            )
            .scalars()
            .all()
        )
        total = session.execute(
            select(func.count())
            .select_from(GovernanceDecision)
            .where(GovernanceDecision.idea_id == idea_id)
        ).scalar_one()

        return {
            "decisions": [
                {
                    "id": d.id,
                    "idea_id": d.idea_id,
                    "decision": d.decision,
                    "reviewer": d.reviewer,
                    "note": d.note,
                    "created_at": str(d.created_at),
                }
                for d in decisions
            ],
            "total": total,
        }


@idea_governance_router.get(
    "/{idea_id}/governance/timeline",
    summary="Governance audit timeline",
    description="Unified read-only timeline of decisions, section revisions, and comments.",
)
async def get_timeline(idea_id: int):
    """Get a unified audit timeline for an idea.

    Aggregates events from:
    - GovernanceDecision (decisions)
    - ProposalSectionRevision (section refinements)
    - Comment (reviewer comments)

    Returns a single sorted list with typed event objects.

    Args:
        idea_id: The idea ID.

    Returns:
        {"events": [...], "total": N}
    """
    events: list[dict] = []

    with get_session() as session:
        # Governance decisions
        decisions = (
            session.execute(
                select(GovernanceDecision)
                .where(GovernanceDecision.idea_id == idea_id)
                .order_by(GovernanceDecision.created_at.asc())
            )
            .scalars()
            .all()
        )
        for d in decisions:
            events.append({
                "type": "decision",
                "timestamp": str(d.created_at),
                "actor": d.reviewer,
                "summary": f"{d.decision.replace('_', ' ').title()}",
                "detail": {
                    "decision": d.decision,
                    "note": d.note,
                },
            })

        # Section revisions (need to resolve proposal via idea_id)
        proposal = session.execute(
            select(Proposal).where(Proposal.idea_id == idea_id)
        ).scalar_one_or_none()

        if proposal:
            revisions = (
                session.execute(
                    select(ProposalSectionRevision)
                    .where(ProposalSectionRevision.proposal_id == proposal.id)
                    .order_by(ProposalSectionRevision.created_at.asc())
                )
                .scalars()
                .all()
            )
            for r in revisions:
                events.append({
                    "type": "section_revision",
                    "timestamp": str(r.created_at),
                    "actor": "system" if r.source == "pipeline" else "user",
                    "summary": f"Section '{r.section_key}' {r.source}",
                    "detail": {
                        "section_key": r.section_key,
                        "source": r.source,
                        "trigger": r.trigger,
                        "section_hash": r.section_hash,
                    },
                })

        # Comments
        comments = (
            session.execute(
                select(Comment)
                .where(Comment.idea_id == idea_id)
                .order_by(Comment.created_at.asc())
            )
            .scalars()
            .all()
        )
        for c in comments:
            events.append({
                "type": "comment",
                "timestamp": str(c.created_at),
                "actor": c.author,
                "summary": f"Comment by {c.author}",
                "detail": {
                    "comment_id": c.id,
                    "content_preview": c.content[:120] if c.content else "",
                    "parent_id": c.parent_id,
                },
            })

    # Sort all events by timestamp (newest first)
    events.sort(key=lambda e: e["timestamp"], reverse=True)

    return {"events": events, "total": len(events)}
