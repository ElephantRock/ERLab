"""Governance approval API routes."""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.api.errors import NotFoundError, ServiceUnavailableError

router = APIRouter()


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
