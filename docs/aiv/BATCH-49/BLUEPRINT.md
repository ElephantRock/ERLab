# BATCH-49 BLUEPRINT — Notification Center + Experiment Runner

**Lead Programmer:** Lead Agent  
**Date:** 2026-05-02  
**AIV Framework:** v5.1  
**Status:** DRAFT  
**Phase:** 2 — Notifications & Experiment Execution

---

## Objective

Deliver a user-visible notification system so pipeline events surface in the UI, and add sandboxed experiment execution capability — closing the competitive gap with AI Scientist.

---

## TASK-01: Notification Center (Backend + Frontend)

### Backend

#### New Model: `NotificationDB` (`backend/db/models.py`)
```python
class NotificationDB(Base):
    __tablename__ = "notifications"
    id: int PK
    user_id: int FK → users.id (nullable — null = broadcast)
    type: String(50)          # pipeline.completed, pipeline.failed, idea.generated, gap.found
    title: String(255)
    message: Text
    read: Boolean default False
    created_at: DateTime default utcnow
    # Indexes: user_id, read, created_at
```

#### New Migration: `alembic/versions/005_notifications.py`
- Create `notifications` table with columns above
- Add indexes on user_id, read, created_at

#### New Route Module: `backend/api/routes/notifications.py`
- `GET /api/v1/notifications/` — List notifications (paginated, filterable by read/unread, ordered by created_at DESC)
- `PATCH /api/v1/notifications/{id}/read` — Mark as read
- `POST /api/v1/notifications/read-all` — Mark all as read
- `GET /api/v1/notifications/stream` — SSE stream for real-time notifications

#### Notification Creation Helper: `backend/notifications/dispatch.py`
- `async def create_notification(type, title, message, user_id=None)` — inserts into DB + pushes to SSE stream
- Wire into existing pipeline hooks:
  - `pipeline.completed` → "Pipeline run completed" with run summary
  - `pipeline.failed` → "Pipeline run failed" with error message
  - `gap.found` → "New research gap discovered"
  - `idea.generated` → "New research idea generated"

#### Register Route in `backend/api/app.py`
- Import and mount at `/api/v1/notifications`

### Frontend

#### New API Client: `frontend/src/api/notifications.ts`
- `getNotifications(params)` — GET with pagination
- `markRead(id)` — PATCH
- `markAllRead()` — POST

#### New Types: add to `frontend/src/api/types.ts`
```typescript
export interface Notification {
  id: number;
  user_id: number | null;
  type: string;
  title: string;
  message: string;
  read: boolean;
  created_at: string;
}
```

#### New Components:
- `frontend/src/components/notifications/notification-bell.tsx` — Bell icon with unread badge count in AppShell header
- `frontend/src/components/notifications/notification-list.tsx` — Dropdown panel with notification items, mark-all-read button

#### Wire into `app-shell.tsx`:
- Add NotificationBell next to Search button in header

### Tests
- Backend: CRUD for notifications, SSE stream, read/unread, mark-all-read (+6 tests)
- Frontend: bell renders, badge shows count, click marks read (+4 tests)

---

## TASK-02: Sandboxed Experiment Execution

### Backend Only (no frontend — API-first)

#### New Module: `backend/pipeline/experiment/`
- `runner.py` — ExperimentRunner class:
  - `async def run(code: str, inputs: dict, timeout: int = 30) -> ExperimentResult`
  - Uses existing `backend/pipeline/sandboxing/` Docker backend for isolation
  - Captures stdout, stderr, exit_code
  - Returns structured ExperimentResult
- `models.py`:
  ```python
  class ExperimentResult(BaseModel):
      success: bool
      stdout: str
      stderr: str
      exit_code: int
      artifacts: dict[str, str]  # name → content
      metrics: dict[str, float]  # name → value
      execution_time_seconds: float
      error: str | None = None
  ```
- `validator.py` — SecurityValidator:
  - Blocks network access (no socket, requests, urllib)
  - Blocks filesystem writes outside /tmp
  - Blocks subprocess spawning
  - Blocks imports of os, sys.exit, eval, exec (except whitelisted)
  - Returns list of violations (empty = safe to run)

#### New Route: `backend/api/routes/experiments.py`
- `POST /api/v1/experiments/run` — Submit code + inputs, returns ExperimentResult
  - Request body: `{ code: str, inputs: dict, timeout?: int, language?: str }`
  - Validates code via SecurityValidator first
  - Runs in Docker sandbox (uses existing sandboxing module)
  - Returns ExperimentResult
- `GET /api/v1/experiments/{id}` — Get cached result (optional, store in memory)

#### Config: Add to `backend/config.py`
```python
experiment_enabled: bool = False  # Disabled by default
experiment_timeout: int = 30
experiment_max_code_size: int = 10000  # bytes
```

#### Register Route in `backend/api/app.py`
- Import and mount at `/api/v1/experiments`

### Tests
- `backend/tests/test_api/test_batch49_task02.py` (+4 tests):
  - Security validator blocks dangerous code
  - Security validator allows safe code
  - Experiment runner returns structured result
  - Timeout is enforced

---

## Acceptance Criteria

| Criterion | Verification |
|:---|:---|
| Notifications table created | Migration 005 runs cleanly |
| GET /notifications returns paginated list | Test assertion |
| PATCH /notifications/{id}/read works | Test assertion |
| SSE stream pushes events | Test assertion |
| Notification bell shows in header | Frontend test |
| Experiment runner executes safe code | Test assertion |
| Security validator blocks dangerous patterns | Test assertion |
| Docker sandbox used for isolation | Code review |
| All existing tests pass | pytest + vitest |

---

*BLUEPRINT — BATCH-49 — AIV Framework v5.1 — Lead Agent*
