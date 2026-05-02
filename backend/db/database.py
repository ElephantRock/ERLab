"""Database engine and session management.

Supports both SQLite (default) and PostgreSQL via the DATABASE_URL setting.
PostgreSQL URLs (postgresql:// or postgresql+psycopg2://) get connection pooling
with pre-ping; SQLite uses the default StaticPool-less mode.
"""

from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import QueuePool

from backend.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


_engine = None
_session_factory = None


def _is_postgresql(url: str) -> bool:
    """Return True if the database URL targets PostgreSQL."""
    return url.startswith("postgresql://") or url.startswith("postgresql+")


def _build_engine_kwargs(url: str, debug: bool) -> dict[str, Any]:
    """Build keyword arguments for ``create_engine`` based on the URL scheme."""
    kwargs: dict[str, Any] = {"echo": debug}
    if _is_postgresql(url):
        kwargs.update(
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
        )
    return kwargs


def create_db_engine():
    """Create a new SQLAlchemy engine from the current settings.

    Uses a connection pool for PostgreSQL and plain mode for SQLite so that
    the default ``sqlite:///./data/elephant_rock.db`` works without extra deps.
    """
    settings = get_settings()
    kwargs = _build_engine_kwargs(settings.database_url, settings.debug)
    return create_engine(settings.database_url, **kwargs)


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def _get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=_get_engine(), expire_on_commit=False)
    return _session_factory


def create_session_factory():
    return _get_session_factory()


def init_db():
    """Create all tables."""
    Base.metadata.create_all(_get_engine())


@contextmanager
def get_session():
    """Provide a transactional scope around a series of operations."""
    session = _get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
