BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID: BATCH-30 | Version: 1.0 | STANDARD | Lead | 2026-05-02

BATCH GOAL: PostgreSQL support + Docker Compose for full stack.
HB-01: SQLite MUST still work. Dual compatibility required.

TASK-01: PostgreSQL Connection Support
  Files: backend/db/database.py (MODIFY — add PostgreSQL connection string support)
         backend/config.py (MODIFY — add database_url config)
         .env.example (MODIFY — add DATABASE_URL example)
  Tests: TEST-30-01-01: SQLite connection works (default)
         TEST-30-01-02: PostgreSQL connection string accepted
         TEST-30-01-03: Connection pool configured correctly
         TEST-30-01-04: Both SQLite and PostgreSQL URLs handled
  Commit: feat(batch-30/task-01): add PostgreSQL connection support

TASK-02: Docker Compose
  Files: docker-compose.yml (NEW — app + postgres + redis services)
         Dockerfile (NEW — multi-stage build)
         .dockerignore (NEW)
  Tests: TEST-30-02-01: Dockerfile builds successfully
         TEST-30-02-02: docker-compose.yml valid YAML
         TEST-30-02-03: Services defined (app, postgres, redis)
         TEST-30-02-04: Health checks configured
  Commit: feat(batch-30/task-02): add Docker Compose configuration

DEPENDENCY: BATCH-28
BASELINE: ~1,806 | Delta: +8 (4 backend + 4 integration) | Target: ~1,814
BAC: ✓ | Lead Sign: Lead + 2026-05-02 11:10
═══════════════════════════════════════════════════════════
