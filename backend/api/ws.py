"""WebSocket endpoint for real-time bidirectional communication (BATCH-50)."""
import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections with channel-based subscriptions."""

    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        await websocket.accept()
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


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint. Clients subscribe to channels via messages."""
    settings = get_settings()
    if not settings.websocket_enabled:
        await websocket.close(code=1008, reason="WebSocket disabled")
        return

    current_channel: str | None = None
    try:
        await websocket.accept()
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
