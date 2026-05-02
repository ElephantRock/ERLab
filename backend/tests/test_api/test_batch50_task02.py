"""BATCH-50 TASK-02: WebSocket Infrastructure tests."""
import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.api.ws import ConnectionManager


def test_50_02_01_connect_adds_to_active():
    """ConnectionManager.connect adds websocket to active channels."""
    mgr = ConnectionManager()
    ws = AsyncMock()
    asyncio.run(mgr.connect(ws, "test-channel"))

    assert "test-channel" in mgr.active
    assert ws in mgr.active["test-channel"]
    assert mgr.total_connections == 1


def test_50_02_02_broadcast_sends_to_subscribers():
    """ConnectionManager.broadcast sends messages to channel subscribers."""
    mgr = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    asyncio.run(mgr.connect(ws1, "ch1"))
    asyncio.run(mgr.connect(ws2, "ch1"))

    message = {"type": "test", "data": "hello"}
    asyncio.run(mgr.broadcast("ch1", message))

    ws1.send_json.assert_called_once_with(message)
    ws2.send_json.assert_called_once_with(message)


def test_50_02_03_disconnect_removes_from_active():
    """ConnectionManager.disconnect removes websocket from active channels."""
    mgr = ConnectionManager()
    ws = AsyncMock()

    asyncio.run(mgr.connect(ws, "ch1"))
    assert "ch1" in mgr.active

    mgr.disconnect(ws, "ch1")
    assert "ch1" not in mgr.active
    assert mgr.total_connections == 0


def test_50_02_04_endpoint_rejects_when_disabled():
    """WebSocket endpoint rejects connection when websocket_enabled=False."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.api.ws import router

    app = FastAPI()
    app.include_router(router)

    mock_settings = MagicMock()
    mock_settings.websocket_enabled = False

    with patch("backend.api.ws.get_settings", return_value=mock_settings):
        client = TestClient(app)
        with pytest.raises(Exception):
            # WebSocket connections are rejected when disabled (code 1008)
            with client.websocket_connect("/ws"):
                pass
