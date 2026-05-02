"""Notification dispatch module (BATCH-49)."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from backend.db.database import get_session
from backend.db.models import NotificationDB

logger = logging.getLogger(__name__)

# Connected SSE clients
_subscribers: set[asyncio.Queue] = set()


async def create_notification(
    type: str, title: str, message: str, user_id: int | None = None
) -> NotificationDB:
    """Create a notification and push to all connected SSE clients."""
    # Insert into DB
    notif = None
    with get_session() as session:
        notif = NotificationDB(
            user_id=user_id, type=type, title=title, message=message
        )
        session.add(notif)
        session.commit()
        session.refresh(notif)

    # Push to SSE subscribers
    payload = {
        "id": notif.id,
        "type": notif.type,
        "title": notif.title,
        "message": notif.message,
        "read": notif.read,
        "created_at": notif.created_at.isoformat(),
    }
    dead_queues: set[asyncio.Queue] = set()
    for queue in _subscribers:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            dead_queues.add(queue)
    _subscribers.difference_update(dead_queues)

    return notif


def subscribe() -> asyncio.Queue:
    """Register a new SSE client. Returns a queue to consume notifications from."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.add(queue)
    return queue


def unsubscribe(queue: asyncio.Queue) -> None:
    """Unregister an SSE client."""
    _subscribers.discard(queue)
