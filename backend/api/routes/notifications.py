"""Notification center API routes (BATCH-49)."""

import asyncio
import json
import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from backend.api.errors import ForbiddenError, NotFoundError, UnauthorizedError

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/",
    summary="List notifications",
    description="List notifications with pagination, filterable by read status.",
)
async def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    read: bool | None = Query(default=None),
):
    """List notifications with pagination.

    Args:
        limit: Maximum number of notifications to return (1-100).
        offset: Number of notifications to skip.
        read: Optional filter for read/unread status.

    Returns:
        {"notifications": [...], "total": N}
    """
    from backend.db.database import get_session
    from backend.db.models import NotificationDB
    from sqlalchemy import select, func

    with get_session() as session:
        # Build query
        query = select(NotificationDB).order_by(NotificationDB.created_at.desc())
        count_query = select(func.count(NotificationDB.id))

        if read is not None:
            query = query.where(NotificationDB.read == read)
            count_query = count_query.where(NotificationDB.read == read)

        total = session.execute(count_query).scalar() or 0
        results = session.execute(query.offset(offset).limit(limit)).scalars().all()

        return {
            "notifications": [
                {
                    "id": n.id,
                    "user_id": n.user_id,
                    "type": n.type,
                    "title": n.title,
                    "message": n.message,
                    "read": n.read,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                }
                for n in results
            ],
            "total": total,
        }


@router.patch(
    "/{notification_id}/read",
    summary="Mark notification as read",
    description="Mark a single notification as read.",
)
async def mark_read(notification_id: int):
    """Mark a notification as read.

    Args:
        notification_id: The notification ID.

    Returns:
        Updated notification object.
    """
    from backend.db.database import get_session
    from backend.db.models import NotificationDB

    with get_session() as session:
        notif = session.query(NotificationDB).filter(NotificationDB.id == notification_id).first()
        if not notif:
            raise NotFoundError("Notification not found")
        notif.read = True
        session.commit()
        session.refresh(notif)
        return {
            "id": notif.id,
            "user_id": notif.user_id,
            "type": notif.type,
            "title": notif.title,
            "message": notif.message,
            "read": notif.read,
            "created_at": notif.created_at.isoformat() if notif.created_at else None,
        }


@router.post(
    "/read-all",
    summary="Mark all notifications as read",
    description="Mark all notifications as read.",
)
async def mark_all_read():
    """Mark all notifications as read.

    Returns:
        {"updated": N} — number of notifications updated.
    """
    from backend.db.database import get_session
    from backend.db.models import NotificationDB

    with get_session() as session:
        count = session.query(NotificationDB).filter(NotificationDB.read == False).update({"read": True})
        session.commit()
        return {"updated": count}


@router.get(
    "/stream",
    summary="Stream notifications via SSE",
    description="Server-Sent Events endpoint for real-time notification streaming.",
)
async def notification_stream(request: Request):
    """SSE endpoint for notification streaming.

    Defence-in-depth auth check (HB-01 pattern).
    """
    # HB-01: Defence-in-depth auth check
    from backend.config import get_settings

    settings = get_settings()
    if settings.api_key:
        api_key = request.headers.get("X-API-Key", "")
        if not api_key or api_key != settings.api_key:
            raise UnauthorizedError(
                detail="SSE endpoint requires valid X-API-Key header",
                hint="Pass the API key via the X-API-Key header",
            )
    if settings.auth_enabled:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise UnauthorizedError(
                detail="SSE endpoint requires Authorization header",
                hint="Pass a Bearer token via the Authorization header",
            )

    from backend.notifications.dispatch import subscribe, unsubscribe

    queue = subscribe()

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
            unsubscribe(queue)

    return StreamingResponse(_stream(), media_type="text/event-stream")
