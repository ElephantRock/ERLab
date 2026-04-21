"""Governance approval API routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
        raise HTTPException(status_code=503, detail="Governance not initialized")
    return _approval_manager


@router.get("/pending")
async def list_pending_approvals():
    """List all pending governance approvals."""
    manager = _get_manager()
    return {"pending": manager.get_pending()}


@router.post("/{decision_id}/approve")
async def approve_decision(decision_id: str):
    """Approve a pending governance decision."""
    manager = _get_manager()
    if not manager.approve(decision_id):
        raise HTTPException(status_code=404, detail=f"No pending approval '{decision_id}'")
    return {"status": "approved", "decision_id": decision_id}


@router.post("/{decision_id}/deny")
async def deny_decision(decision_id: str, body: DenyRequest | None = None):
    """Deny a pending governance decision."""
    manager = _get_manager()
    amendment = body.amendment if body else None
    if not manager.deny(decision_id, amendment=amendment):
        raise HTTPException(status_code=404, detail=f"No pending approval '{decision_id}'")
    return {"status": "denied", "decision_id": decision_id, "amendment": amendment}
