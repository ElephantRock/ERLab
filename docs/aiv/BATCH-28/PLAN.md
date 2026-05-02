# BATCH-28 Execution Plan

## Overview
JWT authentication, User model, login page, role-based access control.

## TASK-01: Backend — User Model + JWT Auth

### Changes:
1. **`backend/config.py`** — Add `auth_enabled: bool = False` and `jwt_secret: str = "dev-secret-change-me"` fields
2. **`backend/db/models.py`** — Add `User` model (id, username, email, hashed_password, role, created_at)
3. **`backend/api/auth.py`** — Rewrite with JWT system (python-jose + passlib), keep backward compat via `auth_enabled` flag
4. **`backend/api/routes/auth.py`** — NEW: register/login/me/users endpoints
5. **`backend/api/app.py`** — Register auth routes, add JWT middleware
6. **`backend/api/errors.py`** — Add ForbiddenError (403) and ConflictError (409)
7. **`pyproject.toml`** — Add `python-jose[cryptography]` and `passlib[bcrypt]`
8. **`backend/tests/test_api/test_auth.py`** — 10 tests

### Auth Flow:
- When `auth_enabled=False` (default): all endpoints work without auth (dev mode)
- When `auth_enabled=True`: JWT required on all `/api/v1/*` routes except `/api/v1/auth/register` and `/api/v1/auth/login`
- Auth routes themselves are always accessible (register/login)
- `verify_api_key` replaced by `get_current_user` dependency

## TASK-02: Frontend — Login Page + Auth Context

### Changes:
1. **`frontend/src/api/auth.ts`** — NEW: API client for auth endpoints
2. **`frontend/src/contexts/auth-context.tsx`** — NEW: auth state management
3. **`frontend/src/pages/login.tsx`** — NEW: login/register form
4. **`frontend/src/App.tsx`** — Add login route, ProtectedRoute wrapper
5. **`frontend/src/main.tsx`** — Wrap with AuthProvider
6. **`frontend/src/__tests__/auth.test.tsx`** — 8 tests

## TASK-03: Frontend — Role-Based UI Elements

### Changes:
1. **`frontend/src/components/auth/role-badge.tsx`** — NEW: role badge component
2. **`frontend/src/pages/settings.tsx`** — Add user management section (admin only)
3. **`frontend/src/__tests__/role-badge.test.tsx`** — 3 tests

## Commits (Sequential):
1. `feat(batch-28/task-01): add JWT auth with User model and role system`
2. `feat(batch-28/task-02): add login page and auth context`
3. `feat(batch-28/task-03): add role-based UI elements`
