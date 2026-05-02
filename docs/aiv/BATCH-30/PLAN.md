# BATCH-30 Execution Plan

## TASK-01: PostgreSQL Connection Support
1. Modify `backend/db/database.py` — add `create_db_engine()` logic that detects PostgreSQL vs SQLite URLs and configures connection pool accordingly
2. Modify `backend/config.py` — add `database_url` field (already exists, default `sqlite:///./data/elephant_rock.db`) — **no changes needed** ✅
3. Modify `.env.example` — add PostgreSQL URL example comment
4. Create `backend/tests/test_db/test_batch30_postgres.py` — 4 tests

## TASK-02: Docker Compose
1. Create `Dockerfile` — multi-stage build (builder → runtime)
2. Create `docker-compose.yml` — app + postgres + redis with health checks
3. Create `.dockerignore`
4. Create `backend/tests/test_integration/test_batch30_docker.py` — 4 tests

## HB-01: SQLite default preserved in all code paths
## Documentation: CHANGELOG update + report to `docs/aiv/BATCH-30/`
