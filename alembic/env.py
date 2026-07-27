"""Alembic environment configuration for Elephant Rock Research Platform.

Uses SQLAlchemy model metadata for autogenerate.
Enables batch mode (render_as_batch=True) for SQLite compatibility (HB-01).
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure project root is on sys.path so `backend` is importable.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Import all models so Base.metadata contains every table.
from backend.db.database import Base  # noqa: E402
from backend.db.models import (  # noqa: E402
    Idea,
    IdeaPaperLink,
    Paper,
    PipelineRun,
    Proposal,
    ResearchGapDB,
    User,
)
from backend.config import get_settings  # noqa: E402

config = context.config

# Interpret the config file for Python logging.
# Phase 4 / 4G: pass disable_existing_loggers=False so alembic's fileConfig()
# does not disable every pre-existing logger in the process (e.g.
# backend.pipeline.gap_analysis.gap_analyzer). When migration tests run in the
# same pytest session as caplog-based tests, the default True broke caplog
# capture for any logger created before the migration ran. The matching
# 'disable_existing_loggers = False' key in alembic.ini documents the intent.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Target metadata for autogenerate.
target_metadata = Base.metadata


def _get_url() -> str:
    """Resolve the database URL from application settings."""
    return get_settings().database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine.  Calls to
    ``context.execute()`` emit the given string to the script output.
    """
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # HB-01: SQLite compatibility
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an Engine and associates a connection with the context.
    """
    connectable = engine_from_config(
        {"sqlalchemy.url": _get_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # HB-01: SQLite compatibility
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
