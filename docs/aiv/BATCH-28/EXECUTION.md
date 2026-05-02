# BATCH-28 Execution Plan

## HB-01 Compliance
- `auth_enabled` defaults to `False` — all endpoints work without tokens in dev mode
- When `True`, JWT middleware validates tokens on all routes except `/api/v1/auth/*` and `/health`

## TASK-01: Backend — User Model + JWT Auth
1. Add `auth_enabled`, `jwt_secret`, `jwt_algorithm`, `jwt_expire_minutes` to `config.py`
2. Add `User` model to `models.py` (id, username, email, hashed_password, role, created_at)
3. Rewrite `backend/api/auth.py` — keep `verify_api_key`, add JWT utilities (create_token, verify_token, get_current_user, require_role)
4. Create `backend/api/routes/auth.py` — POST register, POST login, GET me, GET users (admin)
5. Modify `app.py` — register auth routes + conditional JWT middleware
6. Add `python-jose[cryptography]` and `passlib[bcrypt]` to deps
7. Write 10 tests in `backend/tests/test_api/test_batch28_auth.py`

## TASK-02: Frontend — Login Page + Auth Context
1. Create `frontend/src/api/auth.ts` — API client for auth endpoints
2. Create `frontend/src/contexts/auth-context.tsx` — AuthProvider with user state + token management
3. Create `frontend/src/pages/login.tsx` — login/register form
4. Modify `App.tsx` — add `/login` route + ProtectedRoute wrapper
5. Modify `main.tsx` — wrap with AuthProvider
6. Write 8 tests in `frontend/src/api/__tests__/auth.test.ts` and `frontend/src/contexts/__tests__/auth-context.test.tsx`

## TASK-03: Frontend — Role-Based UI Elements
1. Create `frontend/src/components/auth/role-badge.tsx`
2. Modify `settings.tsx` — add user management section for admin
3. Write 3 tests in `frontend/src/components/auth/__tests__/role-badge.test.tsx`
