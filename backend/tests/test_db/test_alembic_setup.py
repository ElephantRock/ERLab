"""Tests for BATCH-29/TASK-01 — Alembic migration system and db CLI commands.

Test IDs: TEST-29-01-01 through TEST-29-01-05
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy
from sqlalchemy import inspect

from alembic.config import Config as AlembicConfig
from alembic import command

from backend.db.database import Base
from backend.db.models import Idea, Paper, PipelineRun, Proposal, ResearchGapDB, User


# ── Helpers ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _make_alembic_cfg(db_url: str) -> AlembicConfig:
    """Build an Alembic Config that uses the given SQLite URL."""
    ini_path = PROJECT_ROOT / "alembic.ini"
    cfg = AlembicConfig(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _patch_settings(db_url: str):
    """Return a context manager that patches get_settings with *db_url*."""
    mock_settings = MagicMock()
    mock_settings.database_url = db_url
    mock_settings.debug = False
    return patch("backend.config.get_settings", return_value=mock_settings)


# ── TEST-29-01-01: alembic upgrade head creates all tables ──────────


def test_01_upgrade_head_creates_all_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Running ``alembic upgrade head`` must create every model table."""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _make_alembic_cfg(db_url)

    with _patch_settings(db_url):
        command.upgrade(cfg, "head")

    engine = sqlalchemy.create_engine(db_url)
    insp = inspect(engine)
    existing = set(insp.get_table_names())

    expected = {"users", "papers", "ideas", "proposals", "pipeline_runs", "research_gaps"}
    assert expected.issubset(existing), f"Missing tables: {expected - existing}"
    engine.dispose()


# ── TEST-29-01-02: alembic downgrade base drops all tables ──────────


def test_02_downgrade_base_drops_all_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Running ``alembic downgrade base`` must remove all model tables."""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _make_alembic_cfg(db_url)

    # First upgrade to head
    with _patch_settings(db_url):
        command.upgrade(cfg, "head")

    # Then downgrade to base
    with _patch_settings(db_url):
        command.downgrade(cfg, "base")

    engine = sqlalchemy.create_engine(db_url)
    insp = inspect(engine)
    remaining = insp.get_table_names()

    # Model tables should be gone (alembic_version may remain)
    model_tables = {"users", "papers", "ideas", "proposals", "pipeline_runs", "research_gaps"}
    remaining_model = model_tables.intersection(remaining)
    assert remaining_model == set(), f"Tables should be dropped: {remaining_model}"
    engine.dispose()


# ── TEST-29-01-03: erock db upgrade works ────────────────────────────


def test_03_erock_db_upgrade_works(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The ``erock db upgrade`` CLI command must succeed and create tables."""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"

    with _patch_settings(db_url), \
         patch("backend.cli.commands.db._alembic_cfg", return_value=_make_alembic_cfg(db_url)):
        from backend.cli.commands.db import db_upgrade
        db_upgrade(revision="head")

    # Verify tables were created
    engine = sqlalchemy.create_engine(db_url)
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    assert "users" in existing
    assert "papers" in existing
    assert "ideas" in existing
    engine.dispose()


# ── TEST-29-01-04: erock db downgrade works ─────────────────────────


def test_04_erock_db_downgrade_works(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The ``erock db downgrade`` CLI command must succeed and drop tables."""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _make_alembic_cfg(db_url)

    # First, upgrade to head
    with _patch_settings(db_url):
        command.upgrade(cfg, "head")

    # Now test downgrade via CLI
    with _patch_settings(db_url), \
         patch("backend.cli.commands.db._alembic_cfg", return_value=cfg):
        from backend.cli.commands.db import db_downgrade
        db_downgrade(revision="base")

    engine = sqlalchemy.create_engine(db_url)
    insp = inspect(engine)
    remaining = insp.get_table_names()
    model_tables = {"users", "papers", "ideas", "proposals", "pipeline_runs", "research_gaps"}
    remaining_model = model_tables.intersection(remaining)
    assert remaining_model == set(), f"Tables should be dropped: {remaining_model}"
    engine.dispose()


# ── TEST-29-01-05: Initial migration includes all models ────────────


def test_05_migration_includes_all_models():
    """The generated migration must reference all model table names."""
    from alembic.script import ScriptDirectory

    cfg = _make_alembic_cfg("sqlite:///dummy.db")
    script = ScriptDirectory.from_config(cfg)

    # Get the head revision
    head = script.get_current_head()
    assert head is not None, "No migration revisions found — generate the initial migration first"

    # Read the migration source
    rev = script.get_revision(head)
    migration_path = Path(rev.path)
    assert migration_path.exists(), f"Migration file not found: {migration_path}"

    content = migration_path.read_text()

    # Verify all model table names appear in the migration
    expected_tables = [
        "users",
        "papers",
        "ideas",
        "proposals",
        "pipeline_runs",
        "research_gaps",
    ]
    for table in expected_tables:
        assert table in content, f"Table '{table}' not found in migration {migration_path.name}"
