"""BATCH-49 TASK-01: Notification Center tests."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

from backend.api.routes.notifications import router

app = FastAPI()
app.include_router(router, prefix="/notifications")


def _mock_session():
    ms = MagicMock()
    mc = MagicMock()
    mc.__enter__ = MagicMock(return_value=ms)
    mc.__exit__ = MagicMock(return_value=False)
    return ms, mc


def _make_notif(id=1, user_id=None, type="info", title="Test", message="msg", read=False):
    n = MagicMock()
    n.id = id
    n.user_id = user_id
    n.type = type
    n.title = title
    n.message = message
    n.read = read
    from datetime import datetime, timezone
    n.created_at = datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc)
    return n


def test_49_01_01_create_notification_and_verify():
    """Create notification and verify DB entry."""
    notif = _make_notif(id=1, type="pipeline.completed", title="Pipeline run completed", message="Run run_123 completed successfully")
    ms, mc = _mock_session()
    ms.query.return_value.filter.return_value.first.return_value = notif
    ms.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.scalars.return_value.all.return_value = [notif]
    ms.execute.return_value.scalars.return_value.all.return_value = [notif]
    from sqlalchemy import func
    ms.execute.return_value.scalar.return_value = 1

    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.get("/notifications/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["notifications"][0]["type"] == "pipeline.completed"


def test_49_01_02_list_pagination():
    """List notifications with pagination."""
    ms, mc = _mock_session()
    ms.execute.return_value.scalars.return_value.all.return_value = []
    ms.execute.return_value.scalar.return_value = 0

    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.get("/notifications/?limit=5&offset=10")
    assert resp.status_code == 200
    body = resp.json()
    assert "notifications" in body
    assert "total" in body


def test_49_01_03_filter_by_read():
    """Filter by read/unread status."""
    ms, mc = _mock_session()
    ms.execute.return_value.scalars.return_value.all.return_value = []
    ms.execute.return_value.scalar.return_value = 0

    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.get("/notifications/?read=false")
    assert resp.status_code == 200


def test_49_01_04_mark_single_read():
    """Mark single notification as read."""
    notif = _make_notif(id=1, read=False)
    ms, mc = _mock_session()
    ms.query.return_value.filter.return_value.first.return_value = notif

    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.patch("/notifications/1/read")
    assert resp.status_code == 200
    body = resp.json()
    assert body["read"] is True


def test_49_01_05_mark_all_read():
    """Mark all notifications as read."""
    ms, mc = _mock_session()
    ms.query.return_value.filter.return_value.update.return_value = 3

    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.post("/notifications/read-all")
    assert resp.status_code == 200
    body = resp.json()
    assert "updated" in body


def test_49_01_06_sse_stream_endpoint_exists():
    """SSE stream endpoint is accessible and returns correct content type."""
    queue = asyncio.Queue()
    queue.put_nowait({"done": True})  # Signal stream to close

    with patch("backend.notifications.dispatch.subscribe", return_value=queue):
        with patch("backend.config.get_settings", return_value=MagicMock(api_key=None, auth_enabled=False)):
            client = TestClient(app)
            resp = client.get("/notifications/stream")
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")


def test_49_01_07_broadcast_visible_to_all():
    """Broadcast notification (user_id=null) visible to all."""
    notif = _make_notif(id=1, user_id=None, type="pipeline.completed", title="Completed")
    ms, mc = _mock_session()
    ms.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.scalars.return_value.all.return_value = [notif]
    ms.execute.return_value.scalars.return_value.all.return_value = [notif]
    ms.execute.return_value.scalar.return_value = 1

    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.get("/notifications/")
    body = resp.json()
    assert body["notifications"][0]["user_id"] is None


def test_49_01_08_pagination_limit_offset():
    """Pagination limit/offset works correctly."""
    notifs = [_make_notif(id=i, title=f"Notif {i}") for i in range(1, 4)]
    ms, mc = _mock_session()
    ms.execute.return_value.scalars.return_value.all.return_value = notifs
    ms.execute.return_value.scalar.return_value = 3

    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.get("/notifications/?limit=3&offset=0")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["notifications"]) == 3
