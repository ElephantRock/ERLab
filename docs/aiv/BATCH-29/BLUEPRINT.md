BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID: BATCH-29 | Version: 1.0 | STANDARD | Lead | 2026-05-02

BATCH GOAL: Alembic setup, initial migration, CLI commands.
HB-01: SQLite MUST still work for development. No PostgreSQL-only migrations.

TASK-01: Alembic Setup
  Files: alembic.ini (NEW), alembic/ (NEW directory with env.py, versions/)
         backend/cli/commands/db.py (NEW — upgrade/downgrade commands)
         backend/cli/main.py (MODIFY — register db commands)
  Tests: TEST-29-01-01: alembic upgrade head creates all tables
         TEST-29-01-02: alembic downgrade base drops all tables
         TEST-29-01-03: erock db upgrade works
         TEST-29-01-04: erock db downgrade works
         TEST-29-01-05: Initial migration includes all models
  Commit: feat(batch-29/task-01): add Alembic migration system and db CLI commands

TASK-02: Initial Migration + Verification
  Files: alembic/versions/001_initial.py (NEW — auto-generated from models)
         Makefile (MODIFY — add db-migrate target)
  Tests: TEST-29-02-01: Fresh DB + migration = working app
         TEST-29-02-02: Migration is idempotent
         TEST-29-02-03: Data survives migration
  Commit: feat(batch-29/task-02): add initial migration with all tables

DEPENDENCY: BATCH-28
BASELINE: ~1,798 | Delta: +8 backend | Target: ~1,806
BAC: ✓ | Lead Sign: Lead + 2026-05-02 11:10
═══════════════════════════════════════════════════════════
