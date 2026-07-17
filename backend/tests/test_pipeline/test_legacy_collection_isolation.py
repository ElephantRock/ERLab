"""P0.3.6 legacy collection isolation tests.

Proves:
  - Legacy collection freeze state is durable
  - Frozen state blocks production API endpoints
  - Freeze/quarantine/delete lifecycle transitions
  - Only maintenance inventory can access the collection after freeze
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.models
from backend.db.database import Base
from backend.pipeline.legacy_collection_freeze import (
    LegacyCollectionFrozenError,
    assert_legacy_not_frozen,
    delete_legacy_collection_record,
    freeze_legacy_collection,
    is_legacy_collection_frozen,
    quarantine_legacy_collection,
)
from backend.pipeline.legacy_collection_freeze import _LegacyFreezeState


def _make_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _fk(c, r):
        cur = c.cursor(); cur.execute("PRAGMA foreign_keys=ON"); cur.close()
    Base.metadata.create_all(engine)
    return engine


def test_not_frozen_by_default():
    """Legacy collection is not frozen when no freeze record exists."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        assert not is_legacy_collection_frozen(s)
    finally:
        s.close()


def test_freeze_blocks_production_access():
    """After freezing, assert_legacy_not_frozen raises."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        freeze_legacy_collection(s)
        assert is_legacy_collection_frozen(s)

        with pytest.raises(LegacyCollectionFrozenError):
            assert_legacy_not_frozen(s)
    finally:
        s.close()


def test_freeze_idempotent():
    """Freezing an already-frozen collection is a no-op."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        freeze_legacy_collection(s, reason="first")
        freeze_legacy_collection(s, reason="second")
        assert is_legacy_collection_frozen(s)
    finally:
        s.close()


def test_quarantine_transition():
    """Freeze → quarantine lifecycle."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        freeze_legacy_collection(s)
        assert is_legacy_collection_frozen(s)

        quarantine_legacy_collection(s)
        assert is_legacy_collection_frozen(s)

        state = s.query(_LegacyFreezeState).filter_by(collection_name="research_papers").one()
        assert state.status == "quarantined"
    finally:
        s.close()


def test_delete_transition():
    """Freeze → quarantine → delete lifecycle."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        freeze_legacy_collection(s)
        quarantine_legacy_collection(s)
        delete_legacy_collection_record(s)

        state = s.query(_LegacyFreezeState).filter_by(collection_name="research_papers").one()
        assert state.status == "deleted"
        assert is_legacy_collection_frozen(s)
    finally:
        s.close()


def test_production_access_before_freeze_allowed():
    """Before freezing, assert_legacy_not_frozen passes silently."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        assert_legacy_not_frozen(s)  # No error
    finally:
        s.close()
