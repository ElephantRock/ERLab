BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-28
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead
Date Issued:              2026-05-02

BATCH GOAL: JWT authentication, User model, login page, role-based access control.

HB-01: All existing API endpoints MUST require authentication after this Batch.
       New config flag: auth_enabled (default: False for dev compatibility).
       When auth_enabled=False, all endpoints work without tokens (dev mode).

HB-02: Admin role MUST NOT be auto-assigned. First user is promoted manually
       via CLI command or config flag.

DATA MODELS:
  NEW: User table (id, username, email, hashed_password, role, created_at)
  NEW: auth_enabled config flag (default: False)
  NEW: JWT token generation/validation (python-jose + passlib)
  Roles: admin, user (default on registration)

  NEW endpoints:
    POST /api/v1/auth/register → {user, token}
    POST /api/v1/auth/login → {token, user}
    GET  /api/v1/auth/me → {user}
    GET  /api/v1/auth/users → {users[]} (admin only)

DEPENDENCY: BATCH-27
BASELINE: ~1,780 | Delta: +18 (10 backend + 8 frontend) | Target: ~1,798

TASK LIST (SEQUENTIAL):
───────────────────────────────────────────────────────────

TASK-01: Backend — User Model + JWT Auth
  Files: backend/db/models.py (MODIFY — add User model)
         backend/api/auth.py (MODIFY — add JWT + role system)
         backend/api/routes/auth.py (NEW — register/login/me/users)
         backend/api/app.py (MODIFY — register auth routes + middleware)
         backend/config.py (MODIFY — add auth_enabled flag)
  Tests: TEST-28-01-01: POST /auth/register creates user
         TEST-28-01-02: POST /auth/login returns JWT token
         TEST-28-01-03: GET /auth/me returns user info with valid token
         TEST-28-01-04: GET /auth/me returns 401 without token
         TEST-28-01-05: GET /auth/users returns 403 for non-admin
         TEST-28-01-06: auth_enabled=False skips auth (dev mode)
         TEST-28-01-07: Duplicate registration returns 409
         TEST-28-01-08: Invalid credentials return 401
         TEST-28-01-09: Password is hashed (not stored plain)
         TEST-28-01-10: Default role is "user"
  Commit: feat(batch-28/task-01): add JWT auth with User model and role system

TASK-02: Frontend — Login Page + Auth Context
  Files: frontend/src/pages/login.tsx (NEW)
         frontend/src/contexts/auth-context.tsx (NEW)
         frontend/src/api/auth.ts (NEW)
         frontend/src/App.tsx (MODIFY — add login route + protected route wrapper)
  Tests: TEST-28-02-01: Login page renders username/password form
         TEST-28-02-02: Login submit calls API
         TEST-28-02-03: Auth context provides user state
         TEST-28-02-04: Protected route redirects to login when not authed
         TEST-28-02-05: Login success stores token
         TEST-28-02-06: Login error shows message
         TEST-28-02-07: Logout clears token
         TEST-28-02-08: Register form creates account
  Commit: feat(batch-28/task-02): add login page and auth context

TASK-03: Frontend — Role-Based UI Elements
  Files: frontend/src/pages/settings.tsx (MODIFY — add user management for admin)
         frontend/src/components/auth/role-badge.tsx (NEW)
  Tests: TEST-28-03-01: Admin sees user management section
         TEST-28-03-02: Non-admin user does not see user management
         TEST-28-03-03: Role badge shows correct role
  Commit: feat(batch-28/task-03): add role-based UI elements

BAC: BAC-01 Auth works end-to-end | BAC-02 CHANGELOG | BAC-03 docs
LEAD RESPONSE: Inline review. ACCEPT.
HB-01: auth_enabled=False for dev mode (backward compatible).
Lead Sign: Lead + 2026-05-02 10:40

═══════════════════════════════════════════════════════════
