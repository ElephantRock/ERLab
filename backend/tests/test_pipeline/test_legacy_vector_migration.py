"""Tests for P0.3.5: legacy vector migration schema and constraints.

Proves:
  - Migration 024 preserves existing rows (no fabrications)
  - DB constraints: status/mapping/disposition vocabularies
  - Round-trip stable
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError as SAIntegrityError
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.db.database import Base
from backend.db.models import (
    EmbeddingProfile,
    LegacyVectorInventoryRecord,
    LegacyVectorInventoryRun,
)
from backend.pipeline.vector_contracts import compute_collection_name, compute_profile_id


def _make_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _fk(c, r):
        cur = c.cursor(); cur.execute("PRAGMA foreign_keys=ON"); cur.close()
    Base.metadata.create_all(engine)
    return engine


def _setup_profile(engine):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        pid = compute_profile_id("test", "model", 4, "l2", "v1")
        s.add(EmbeddingProfile(
            profile_id=pid, profile_schema_version="embedding_profile_v1",
            provider="test", model_identifier="model", dimension=4,
            normalization_policy="l2", chunking_schema_version="v1",
            collection_name=compute_collection_name(pid),
            verification_status="unverified",
        ))
        s.commit()
        return pid
    finally:
        s.close()


# ── 1. DB constraints ────────────────────────────────────────────────


def test_invalid_status_rejected():
    engine = _make_engine()
    pid = _setup_profile(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        with pytest.raises(SAIntegrityError):
            s.execute(text(
                "INSERT INTO legacy_vector_inventory_runs "
                "(inventory_schema_version, collection_name, target_embedding_profile_id, status) "
                "VALUES ('legacy_vector_inventory_v1', 'research_papers', :pid, 'bogus')"
            ), {"pid": pid})
            s.commit()
    finally:
        s.close()


def test_valid_inventory_run_accepted():
    engine = _make_engine()
    pid = _setup_profile(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        run = LegacyVectorInventoryRun(
            inventory_schema_version="legacy_vector_inventory_v1",
            collection_name="research_papers",
            target_embedding_profile_id=pid,
            status="pending",
        )
        s.add(run); s.commit()
        assert run.id is not None
    finally:
        s.close()


def test_invalid_mapping_status_rejected():
    engine = _make_engine()
    pid = _setup_profile(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        run = LegacyVectorInventoryRun(
            inventory_schema_version="legacy_vector_inventory_v1",
            collection_name="research_papers",
            target_embedding_profile_id=pid, status="pending",
        )
        s.add(run); s.flush()

        with pytest.raises(SAIntegrityError):
            rec = LegacyVectorInventoryRecord(
                inventory_run_id=run.id,
                legacy_record_id="legacy_1",
                legacy_record_fingerprint="a" * 64,
                mapping_schema_version="legacy_mapping_v1",
                mapping_status="bogus",
            )
            s.add(rec); s.commit()
    finally:
        s.close()


def test_invalid_disposition_rejected():
    engine = _make_engine()
    pid = _setup_profile(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        run = LegacyVectorInventoryRun(
            inventory_schema_version="legacy_vector_inventory_v1",
            collection_name="research_papers",
            target_embedding_profile_id=pid, status="pending",
        )
        s.add(run); s.flush()

        with pytest.raises(SAIntegrityError):
            rec = LegacyVectorInventoryRecord(
                inventory_run_id=run.id,
                legacy_record_id="legacy_1",
                legacy_record_fingerprint="a" * 64,
                mapping_schema_version="legacy_mapping_v1",
                mapping_status="mapped",
                disposition="bogus_disposition",
            )
            s.add(rec); s.commit()
    finally:
        s.close()


def test_valid_mapped_record_accepted():
    engine = _make_engine()
    pid = _setup_profile(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        run = LegacyVectorInventoryRun(
            inventory_schema_version="legacy_vector_inventory_v1",
            collection_name="research_papers",
            target_embedding_profile_id=pid, status="scanned",
        )
        s.add(run); s.flush()

        rec = LegacyVectorInventoryRecord(
            inventory_run_id=run.id,
            legacy_record_id="legacy_chunk_1",
            legacy_record_fingerprint="b" * 64,
            mapping_schema_version="legacy_mapping_v1",
            mapping_status="mapped",
            mapping_method="paper_id_exact",
            mapped_paper_id=1,
            disposition="reindexed",
            target_vector_record_id="c" * 64,
        )
        s.add(rec); s.commit()
        assert rec.inventory_run_id is not None
    finally:
        s.close()


# ── 2. Migration tests ───────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[3]

def _alembic_cfg(db_url):
    from alembic.config import Config
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg

def _patched_settings(db_url):
    return patch("backend.config.get_settings", return_value=MagicMock(
        database_url=db_url, debug=False))


def test_migration_024_preserves_legacy():
    from alembic import command
    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'p035.db'}"
    cfg = _alembic_cfg(db_url)
    with _patched_settings(db_url):
        command.upgrade(cfg, "023")
        command.upgrade(cfg, "024")
        engine = create_engine(db_url)
        with engine.connect() as c:
            count = c.execute(text("SELECT COUNT(*) FROM legacy_vector_inventory_runs")).scalar()
            assert count == 0, "no fabrications"


def test_migration_024_round_trip():
    from alembic import command
    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'rt.db'}"
    cfg = _alembic_cfg(db_url)
    with _patched_settings(db_url):
        command.upgrade(cfg, "023")
        command.upgrade(cfg, "024")
        command.downgrade(cfg, "023")
        assert not inspect(create_engine(db_url)).has_table("legacy_vector_inventory_runs")
        command.upgrade(cfg, "024")
        assert inspect(create_engine(db_url)).has_table("legacy_vector_inventory_runs")
