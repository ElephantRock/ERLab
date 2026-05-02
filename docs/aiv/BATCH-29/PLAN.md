# BATCH-29 Execution Plan

## Overview
Set up Alembic migration system, create CLI db commands, generate initial migration.

## TASK-01: Alembic Setup

### Files to create:
1. **`alembic.ini`** — Alembic config pointing to `alembic/` dir, using config.py for DB URL
2. **`alembic/env.py`** — Configured to use `backend.db.models.Base` as target_metadata, SQLite-compatible
3. **`alembic/versions/.gitkeep`** — Empty versions directory
4. **`alembic/script.py.mako`** — Standard migration template
5. **`backend/cli/commands/db.py`** — `upgrade` and `downgrade` CLI commands using Alembic API
6. **Modify `backend/cli/main.py`** — Register db subcommand group

### Tests (5):
- TEST-29-01-01: alembic upgrade head creates all tables
- TEST-29-01-02: alembic downgrade base drops all tables
- TEST-29-01-03: erock db upgrade works
- TEST-29-01-04: erock db downgrade works
- TEST-29-01-05: Initial migration includes all models

### Commit: `feat(batch-29/task-01): add Alembic migration system and db CLI commands`

## TASK-02: Initial Migration + Verification

### Files to create:
1. **`alembic/versions/001_initial.py`** — Auto-generated from models (all 7 tables)
2. **Modify `Makefile`** — Add `db-migrate` target

### Tests (3):
- TEST-29-02-01: Fresh DB + migration = working app
- TEST-29-02-02: Migration is idempotent
- TEST-29-02-03: Data survives migration

### Commit: `feat(batch-29/task-02): add initial migration with all tables`

## HB-01: SQLite Compatibility
- All migrations use SQLite-compatible operations (no PostgreSQL-specific features)
- `render_as_batch=True` in env.py for SQLite ALTER TABLE support

## Dependency Check:
- `alembic>=1.13` already in pyproject.toml dependencies ✓
