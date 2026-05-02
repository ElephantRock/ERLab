"""Tests for BATCH-38/TASK-01: Database Schema Migration.

Test IDs: TEST-38-01-01 through TEST-38-01-03

Covers:
- TEST-38-01-01: Migration upgrade creates all 5 new columns
- TEST-38-01-02: Migration downgrade removes all 5 new columns
- TEST-38-01-03: Existing data survives migration roundtrip
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

from alembic.config import Config as AlembicConfig
from alembic import command

from backend.db.database import Base
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


# ── TEST-38-01-01: Migration upgrade creates all 5 new columns ──────


def test_38_01_01_upgrade_creates_all_five_columns(tmp_path: Path):
    """Migration upgrade must create all 5 new columns with correct types."""
    db_path = tmp_path / "upgrade_test.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _make_alembic_cfg(db_url)

    with _patch_settings(db_url):
        command.upgrade(cfg, "head")

    engine = sqlalchemy.create_engine(db_url)
    insp = inspect(engine)

    # Check research_gaps table has new columns
    gap_columns = {col["name"] for col in insp.get_columns("research_gaps")}
    assert "truth_frequency" in gap_columns, "truth_frequency column missing"
    assert "truth_confidence" in gap_columns, "truth_confidence column missing"
    assert "truth_evidence_count" in gap_columns, "truth_evidence_count column missing"
    assert "related_clusters" in gap_columns, "related_clusters column missing"

    # Check pipeline_runs table has new column
    run_columns = {col["name"] for col in insp.get_columns("pipeline_runs")}
    assert "cluster_report_json" in run_columns, "cluster_report_json column missing"

    engine.dispose()


# ── TEST-38-01-02: Migration downgrade removes all 5 new columns ────


def test_38_01_02_downgrade_removes_all_five_columns(tmp_path: Path):
    """Migration downgrade must remove all 5 new columns."""
    db_path = tmp_path / "downgrade_test.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _make_alembic_cfg(db_url)

    # First upgrade to head
    with _patch_settings(db_url):
        command.upgrade(cfg, "head")

    # Then downgrade by 1 (back to initial)
    with _patch_settings(db_url):
        command.downgrade(cfg, "-1")

    engine = sqlalchemy.create_engine(db_url)
    insp = inspect(engine)

    # Check research_gaps table does NOT have new columns
    gap_columns = {col["name"] for col in insp.get_columns("research_gaps")}
    assert "truth_frequency" not in gap_columns
    assert "truth_confidence" not in gap_columns
    assert "truth_evidence_count" not in gap_columns
    assert "related_clusters" not in gap_columns

    # Check pipeline_runs table does NOT have new column
    run_columns = {col["name"] for col in insp.get_columns("pipeline_runs")}
    assert "cluster_report_json" not in run_columns

    engine.dispose()


# ── TEST-38-01-03: Existing data survives migration roundtrip ───────


def test_38_01_03_existing_data_survives_roundtrip(tmp_path: Path):
    """Data inserted before the 002 migration must survive upgrade/downgrade roundtrip."""
    db_path = tmp_path / "roundtrip_test.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _make_alembic_cfg(db_url)

    # Step 1: Upgrade to initial migration only
    with _patch_settings(db_url):
        command.upgrade(cfg, "29607f14fd7f")

    engine = sqlalchemy.create_engine(db_url)
    with engine.connect() as conn:
        # Insert baseline data using raw SQL (table doesn't have new columns yet)
        conn.execute(sqlalchemy.text(
            "INSERT INTO pipeline_runs (status, domain, config_json, stages_completed, created_at) "
            "VALUES ('pending', 'AI/NLP', '{}', '[]', datetime('now'))"
        ))
        result = conn.execute(sqlalchemy.text("SELECT last_insert_rowid()"))
        run_id = result.scalar()

        conn.execute(sqlalchemy.text(
            "INSERT INTO research_gaps (title, description, gap_type, confidence, potential_impact, pipeline_run_id, created_at) "
            "VALUES ('Pre-existing Gap', 'A gap created before migration', '', 0.75, '', :run_id, datetime('now'))"
        ), {"run_id": run_id})
        result = conn.execute(sqlalchemy.text("SELECT last_insert_rowid()"))
        gap_id = result.scalar()

        conn.execute(sqlalchemy.text(
            "INSERT INTO ideas (title, problem_statement, proposed_method, expected_contributions, domain, pipeline_run_id, created_at) "
            "VALUES ('Pre-existing Idea', 'P', 'M', 'C', 'AI/NLP', :run_id, datetime('now'))"
        ), {"run_id": run_id})
        result = conn.execute(sqlalchemy.text("SELECT last_insert_rowid()"))
        idea_id = result.scalar()

        conn.commit()

    # Step 2: Upgrade to head (applies 002_gap_enrichment)
    with _patch_settings(db_url):
        command.upgrade(cfg, "head")

    # Step 3: Verify data still exists after upgrade (ORM now works with new schema)
    Session = sessionmaker(bind=engine)
    session = Session()

    found_run = session.get(PipelineRun, run_id)
    assert found_run is not None
    assert found_run.domain == "AI/NLP"

    found_gap = session.get(ResearchGapDB, gap_id)
    assert found_gap is not None
    assert found_gap.title == "Pre-existing Gap"
    assert found_gap.confidence == 0.75
    # Verify new columns have default values (HB-01)
    assert found_gap.truth_frequency == 0.5
    assert found_gap.truth_confidence == 0.5
    assert found_gap.truth_evidence_count == 0
    assert found_gap.related_clusters is None

    found_idea = session.get(Idea, idea_id)
    assert found_idea is not None
    assert found_idea.title == "Pre-existing Idea"

    session.close()
    engine.dispose()
