"""WebSocket endpoint for real-time bidirectional communication (BATCH-50).

Security: JWT authentication required on connection. Clients must provide
a valid token via query parameter (?token=...) or as the first message
with action "auth".
"""
import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from backend.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections with channel-based subscriptions."""

    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        self.active.setdefault(channel, []).append(websocket)
        logger.info("WS connected to channel=%s (%d clients)", channel, len(self.active[channel]))

    def disconnect(self, websocket: WebSocket, channel: str) -> None:
        if channel in self.active:
            try:
                self.active[channel].remove(websocket)
            except ValueError:
                pass
            if not self.active[channel]:
                del self.active[channel]

    async def broadcast(self, channel: str, message: dict[str, Any]) -> None:
        if channel not in self.active:
            return
        dead: list[WebSocket] = []
        for ws in self.active[channel]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, channel)

    @property
    def total_connections(self) -> int:
        return sum(len(conns) for conns in self.active.values())


manager = ConnectionManager()


def _validate_ws_token(token: str | None) -> bool:
    """Validate a JWT or API key for WebSocket auth.

    Returns True if token is valid (or auth is disabled).
    Returns False if token is invalid.
    """
    if not token:
        return False

    settings = get_settings()

    # Try JWT first
    try:
        from backend.api.auth import decode_access_token
        payload = decode_access_token(token)
        if payload.get("sub"):
            return True
    except Exception:
        pass

    # Fallback: API key
    if settings.api_key and token == settings.api_key:
        return True

    return False


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(default=None),
):
    """Main WebSocket endpoint. Requires JWT or API key authentication.

    Auth methods (any one suffices):
    1. Query parameter: ws://host/ws?token=<jwt_or_api_key>
    2. First message: {"action": "auth", "token": "<jwt_or_api_key>"}

    After auth, clients subscribe to channels via:
    {"action": "subscribe", "channel": "<name>"}
    """
    settings = get_settings()
    if not settings.websocket_enabled:
        await websocket.close(code=1008, reason="WebSocket disabled")
        return

    # Phase 1: Accept and authenticate
    await websocket.accept()

    # Check query parameter token first
    authenticated = _validate_ws_token(token)

    # If not authenticated via query param, wait for auth message
    if not authenticated:
        try:
            # Give client 5 seconds to send auth message
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            msg = json.loads(raw)
            if msg.get("action") == "auth":
                auth_token = msg.get("token")
                authenticated = _validate_ws_token(auth_token)
            else:
                # First message wasn't auth — reject
                await websocket.send_json({"type": "error", "message": "Authentication required"})
                await websocket.close(code=4001, reason="Authentication required")
                return
        except asyncio.TimeoutError:
            await websocket.send_json({"type": "error", "message": "Auth timeout"})
            await websocket.close(code=4001, reason="Authentication timeout")
            return
        except (json.JSONDecodeError, Exception):
            await websocket.close(code=4002, reason="Invalid auth message")
            return

    if not authenticated:
        await websocket.send_json({"type": "error", "message": "Invalid token"})
        await websocket.close(code=4003, reason="Invalid credentials")
        return

    await websocket.send_json({"type": "auth_ok"})

    # Phase 2: Authenticated — handle channel subscriptions
    current_channel: str | None = None
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            action = msg.get("action")
            if action == "subscribe":
                # Unsubscribe from previous channel
                if current_channel:
                    manager.disconnect(websocket, current_channel)
                current_channel = msg.get("channel", "global")
                await manager.connect(websocket, current_channel)
                await websocket.send_json({"type": "subscribed", "channel": current_channel})
            elif action == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json({"type": "error", "message": f"Unknown action: {action}"})
    except WebSocketDisconnect:
        if current_channel:
            manager.disconnect(websocket, current_channel)
        logger.info("WS disconnected from channel=%s", current_channel)
