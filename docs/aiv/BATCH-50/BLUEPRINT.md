# BATCH-50 BLUEPRINT — i18n Locales + WebSocket Infrastructure

**Lead Programmer:** Lead Agent  
**Date:** 2026-05-02  
**AIV Framework:** v5.1  
**Phase:** 3 — Internationalization & Real-time

---

## Objective

Add Chinese (zh) and Spanish (es) translations to the existing i18n infrastructure, and add WebSocket support for bidirectional real-time communication alongside existing SSE.

---

## TASK-01: Chinese + Spanish Translations

### Target Files (NEW)
- `frontend/src/i18n/zh.json` — Full Chinese translation
- `frontend/src/i18n/es.json` — Full Spanish translation

### Target Files (MODIFY)
- `frontend/src/i18n/config.ts` — Register zh and es resources
- `frontend/src/components/i18n/language-switcher.tsx` — Show 3 language options

### Specification

1. Read `frontend/src/i18n/en.json` to understand the complete key structure
2. Create `zh.json` with Chinese translations for every key in `en.json`
3. Create `es.json` with Spanish translations for every key in `en.json`
4. Update `config.ts`:
   ```typescript
   import zh from "./zh.json";
   import es from "./es.json";
   // Add to resources:
   zh: { translation: zh },
   es: { translation: es },
   ```
5. Update `language-switcher.tsx` to show 3 options: English, 中文, Español

### Key categories to translate
- Navigation labels (Dashboard, Pipeline, Ideas, Gaps, etc.)
- Page titles and headings
- Button labels (Search, Export, Save, etc.)
- Status labels (Running, Completed, Failed)
- Form labels and placeholders
- Error messages
- Empty state messages

### Tests
- Language switching test (switch to zh, verify Chinese text renders)
- Fallback test (missing key falls back to English)
- Locale detection test

---

## TASK-02: WebSocket Infrastructure

### Backend

#### New Module: `backend/api/ws.py`

```python
from fastapi import WebSocket, WebSocketDisconnect, Depends
from backend.api.auth import verify_token_ws
from backend.config import get_settings

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}  # channel → [ws]
    
    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)
    
    def disconnect(self, websocket: WebSocket, channel: str):
        if channel in self.active_connections:
            self.active_connections[channel].remove(websocket)
    
    async def broadcast(self, channel: str, message: dict):
        if channel in self.active_connections:
            dead = []
            for ws in self.active_connections[channel]:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.active_connections[channel].remove(ws)

manager = ConnectionManager()

@router.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Auth check (optional — if auth_enabled)
    # Accept connection
    # Channel subscription via first message: {"action": "subscribe", "channel": "pipeline:123"}
    # Loop: receive messages, dispatch to handlers
    # On disconnect: cleanup
```

Message types:
- Client → Server: `{"action": "subscribe", "channel": "pipeline:{id}"}`
- Server → Client: `{"type": "pipeline.progress", "data": {...}}`
- Server → Client: `{"type": "notification.new", "data": {...}}`

#### Config Addition (`backend/config.py`)
```python
websocket_enabled: bool = True
```

#### Register in `backend/api/app.py`

#### Wire into pipeline progress:
- In `backend/api/routes/pipeline.py`, when pipeline progresses, also broadcast via WebSocket manager (if websocket_enabled)
- The SSE progress endpoint stays — WebSocket is supplementary, not replacement

### Frontend

#### New Hook: `frontend/src/hooks/useWebSocket.ts`

```typescript
export function useWebSocket(channel?: string) {
  // Connect to ws://host/api/v1/ws
  // Subscribe to channel on connect
  // Return { messages, connected, send }
  // Auto-reconnect on disconnect (exponential backoff)
  // Fallback: if WebSocket fails, do nothing (SSE still works)
}
```

#### Wire into RunDetailPage:
- Import useWebSocket hook
- Subscribe to `pipeline:{runId}` channel
- Display connection status indicator
- Use incoming progress messages to update stage display (in addition to SSE polling)

### Tests
- Backend: ConnectionManager connect/disconnect/broadcast (+3 tests)
- Backend: WebSocket endpoint rejects unauthenticated when auth enabled (+1 test)
- Frontend: useWebSocket hook connects and receives messages (+2 tests)

---

## Acceptance Criteria

| Criterion | Verification |
|:---|:---|
| zh.json has all keys from en.json | Key count matches |
| es.json has all keys from en.json | Key count matches |
| Language switcher shows 3 options | Visual check / test |
| WebSocket endpoint accepts connections | Test |
| ConnectionManager broadcasts to subscribers | Test |
| useWebSocket hook works with fallback | Test |
| All existing tests pass | pytest + vitest |

---

*BLUEPRINT — BATCH-50 — AIV Framework v5.1 — Lead Agent*
