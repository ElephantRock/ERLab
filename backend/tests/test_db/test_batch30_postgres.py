"""Tests for BATCH-30/TASK-01 — PostgreSQL connection support.

Test IDs: TEST-30-01-01 through TEST-30-01-04
HB-01: SQLite MUST still work as the default.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy

from backend.db.database import (
    Base,
    _build_engine_kwargs,
    _is_postgresql,
    create_db_engine,
)

# ── TEST-30-01-01: SQLite connection works (default) ────────────────


def test_01_sqlite_connection_works(tmp_path):
    """SQLite engine must be created and usable with the default URL."""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"

    mock_settings = MagicMock()
    mock_settings.database_url = db_url
    mock_settings.debug = False

    with patch("backend.db.database.get_settings", return_value=mock_settings):
        engine = create_db_engine()

    assert engine is not None
    assert "sqlite" in str(engine.url)

    # Verify the engine can actually connect and create tables
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        result = conn.execute(sqlalchemy.text("SELECT 1"))
        assert result.scalar() == 1
    engine.dispose()


# ── TEST-30-01-02: PostgreSQL connection string accepted ────────────


def test_02_postgresql_connection_string_accepted():
    """A PostgreSQL URL must be recognized and produce engine kwargs with pool config.

    Verifies that ``_is_postgresql`` and ``_build_engine_kwargs`` produce the
    correct pool configuration without actually importing a PostgreSQL driver.
    """
    pg_url = "postgresql+psycopg2://erock:secret@localhost:5432/elephant_rock"

    # Verify classification
    assert _is_postgresql(pg_url) is True

    # Verify engine kwargs
    kwargs = _build_engine_kwargs(pg_url, debug=False)
    assert kwargs["poolclass"] is sqlalchemy.pool.QueuePool
    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 10
    assert kwargs["pool_pre_ping"] is True

    # Verify the full pipeline via create_db_engine with a generic dialect
    generic_url = "postgresql://erock:secret@localhost:5432/elephant_rock"
    mock_settings = MagicMock()
    mock_settings.database_url = generic_url
    mock_settings.debug = False

    # Patch create_engine to capture the call args (avoids driver import)
    with patch("backend.db.database.get_settings", return_value=mock_settings), \
         patch("backend.db.database.create_engine") as mock_create:
        mock_create.return_value = MagicMock()
        create_db_engine()
        mock_create.assert_called_once()
        call_url = mock_create.call_args[0][0]
        call_kwargs = mock_create.call_args[1]
        assert "postgresql" in call_url
        assert call_kwargs["poolclass"] is sqlalchemy.pool.QueuePool
        assert call_kwargs["pool_pre_ping"] is True


# ── TEST-30-01-03: Connection pool configured correctly ─────────────


def test_03_connection_pool_configured_correctly():
    """PostgreSQL URLs must use QueuePool with pre-ping enabled."""
    pg_url = "postgresql://user:pass@db:5432/mydb"
    kwargs = _build_engine_kwargs(pg_url, debug=False)

    assert kwargs["poolclass"] is sqlalchemy.pool.QueuePool
    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 10
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_recycle"] == 300

    # SQLite should NOT have pool settings
    sqlite_url = "sqlite:///./data/test.db"
    sqlite_kwargs = _build_engine_kwargs(sqlite_url, debug=False)
    assert "poolclass" not in sqlite_kwargs
    assert "pool_size" not in sqlite_kwargs


# ── TEST-30-01-04: Both SQLite and PostgreSQL URLs handled ──────────


@pytest.mark.parametrize(
    "url, expected",
    [
        ("sqlite:///./data/elephant_rock.db", False),
        ("sqlite://", False),
        ("postgresql://user:pass@host/db", True),
        ("postgresql+psycopg2://user:pass@host/db", True),
        ("postgresql+pg8000://user:pass@host/db", True),
    ],
)
def test_04_both_url_schemes_detected(url, expected):
    """``_is_postgresql`` must correctly classify SQLite vs PostgreSQL URLs."""
    assert _is_postgresql(url) is expected

    # Verify _build_engine_kwargs returns valid dicts for all schemes
    kwargs = _build_engine_kwargs(url, debug=True)
    assert kwargs["echo"] is True
    if expected:
        assert "poolclass" in kwargs
    else:
        assert "poolclass" not in kwargs
