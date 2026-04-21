"""Database engine and session management."""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


_engine = None
_session_factory = None


def create_db_engine():
    settings = get_settings()
    return create_engine(settings.database_url, echo=settings.debug)


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
