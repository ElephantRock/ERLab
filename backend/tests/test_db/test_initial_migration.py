"""Tests for BATCH-29/TASK-02 — Initial migration with all tables.

Test IDs: TEST-29-02-01 through TEST-29-02-03
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import sqlalchemy
from alembic.config import Config as AlembicConfig
from sqlalchemy import inspect

from alembic import command
from backend.db.models import Idea, Paper, PipelineRun, ResearchGapDB, User

# ── Helpers ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _make_alembic_cfg(db_url: str) -> AlembicConfig:
    ini_path = PROJECT_ROOT / "alembic.ini"
    cfg = AlembicConfig(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _patch_settings(db_url: str):
    mock_settings = MagicMock()
    mock_settings.database_url = db_url
    mock_settings.debug = False
    return patch("backend.config.get_settings", return_value=mock_settings)


# ── TEST-29-02-01: Fresh DB + migration = working app ───────────────


def test_01_fresh_db_migration_working_app(tmp_path: Path):
    """A freshly migrated DB must allow CRUD operations on all models."""
    db_path = tmp_path / "app.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _make_alembic_cfg(db_url)

    # Apply migrations
    with _patch_settings(db_url):
        command.upgrade(cfg, "head")

    # Verify we can insert and query via SQLAlchemy
    engine = sqlalchemy.create_engine(db_url)
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Insert a user
        user = User(username="alice", email="alice@test.com", hashed_password="hash123")
        session.add(user)
        session.commit()
        assert user.id is not None

        # Insert a paper
        paper = Paper(source_id="ss-001", source="semantic_scholar", title="Test Paper")
        session.add(paper)
        session.commit()
        assert paper.id is not None

        # Insert a pipeline run
        run = PipelineRun(domain="AI/NLP", provenance_version="pre_provenance",
                          legacy_provenance_reason="pre_gating_run")
        session.add(run)
        session.commit()
        assert run.id is not None

        # Insert an idea linked to the run
        idea = Idea(
            title="Test Idea",
            problem_statement="Test problem",
            proposed_method="Test method",
            expected_contributions="Test contrib",
            pipeline_run_id=run.id,
        )
        session.add(idea)
        session.commit()
        assert idea.id is not None

        # Insert a research gap linked to the run
        gap = ResearchGapDB(
            title="Test Gap", description="A gap", pipeline_run_id=run.id
        )
        session.add(gap)
        session.commit()
        assert gap.id is not None

        # Query back
        assert session.query(User).count() == 1
        assert session.query(Paper).count() == 1
        assert session.query(Idea).count() == 1
    finally:
        session.close()
        engine.dispose()


# ── TEST-29-02-02: Migration is idempotent ──────────────────────────


def test_02_migration_idempotent(tmp_path: Path):
    """Running upgrade head twice must succeed without error."""
    db_path = tmp_path / "idempotent.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _make_alembic_cfg(db_url)

    with _patch_settings(db_url):
        # First upgrade
        command.upgrade(cfg, "head")

        # Second upgrade (idempotent)
        command.upgrade(cfg, "head")

    engine = sqlalchemy.create_engine(db_url)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert "users" in tables
    assert "papers" in tables
    engine.dispose()


# ── TEST-29-02-03: Data survives migration ──────────────────────────


def test_03_data_survives_migration(tmp_path: Path):
    """Data inserted before a re-migration must survive."""
    db_path = tmp_path / "survive.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _make_alembic_cfg(db_url)

    # First: create tables via migration and insert data
    with _patch_settings(db_url):
        command.upgrade(cfg, "head")

    engine = sqlalchemy.create_engine(db_url)
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine)
    session = Session()

    user = User(username="bob", email="bob@test.com", hashed_password="pw")
    session.add(user)
    session.commit()
    user_id = user.id
    session.close()

    # Now run migration again (idempotent upgrade)
    with _patch_settings(db_url):
        command.upgrade(cfg, "head")

    # Verify data still exists
    session = Session()
    found = session.query(User).filter_by(id=user_id).first()
    assert found is not None
    assert found.username == "bob"
    assert found.email == "bob@test.com"
    session.close()
    engine.dispose()
