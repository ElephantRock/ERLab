"""Database engine and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


def create_db_engine():
    settings = get_settings()
    return create_engine(settings.database_url, echo=settings.debug)


def create_session_factory():
    engine = create_db_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(create_db_engine())
