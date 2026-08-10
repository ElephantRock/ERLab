"""Tests for BATCH-38/TASK-02: Update Persistence Layer.

Test IDs: TEST-38-02-01 through TEST-38-02-05

Covers:
- TEST-38-02-01: persist_gaps writes truth_frequency to DB
- TEST-38-02-02: persist_gaps writes related_clusters as JSON to DB
- TEST-38-02-03: persist_cluster_report writes cluster_report_json to PipelineRun
- TEST-38-02-04: load_gaps reconstructs ResearchGap with truth values
- TEST-38-02-05: Full roundtrip: persist → load → assert equality (HB-03)
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.database import Base
from backend.db.models import PipelineRun, ResearchGapDB
from backend.pipeline.gap_analysis.models import ClusterInfo, ClusterReport, ResearchGap
from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.persistence import PipelinePersistence

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    """Create an in-memory SQLite session with all tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def persistence():
    return PipelinePersistence()


@pytest.fixture
def db_run_id(db_session):
    """Create a pipeline run and return its ID."""
    run = PipelineRun(domain="AI/NLP", provenance_version="pre_provenance", legacy_provenance_reason="pre_gating_run")
    db_session.add(run)
    db_session.commit()
    return run.id


def _mock_session_context(db_session):
    """Create a mock context manager that yields the real db_session."""
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=db_session)
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


def _make_result(gaps: list[ResearchGap]):
    """Create a result-like object with a gaps attribute."""
    return SimpleNamespace(gaps=gaps)


# ── TEST-38-02-01: persist_gaps writes truth_frequency to DB ──────────


def test_38_02_01_persist_gaps_writes_truth_frequency(db_session, db_run_id, persistence):
    """persist_gaps must write truth_frequency from TruthValue to the DB."""
    gap = ResearchGap(
        title="Truth Test Gap",
        description="Testing truth persistence",
        gap_type="methodological",
        confidence=0.8,
        truth=TruthValue(frequency=0.72, confidence=0.85, evidence_count=5),
    )

    with patch("backend.db.database.get_session", return_value=_mock_session_context(db_session)):
        persistence.persist_gaps(_make_result([gap]), db_run_id)

    # Verify the data was written
    db_gap = db_session.query(ResearchGapDB).first()
    assert db_gap is not None
    assert db_gap.truth_frequency == 0.72
    assert db_gap.truth_confidence == 0.85
    assert db_gap.truth_evidence_count == 5


# ── TEST-38-02-02: persist_gaps writes related_clusters as JSON ──────


def test_38_02_02_persist_gaps_writes_related_clusters_json(db_session, db_run_id, persistence):
    """persist_gaps must write related_clusters as JSON array string to the DB."""
    gap = ResearchGap(
        title="Cluster Gap",
        description="Gap with related clusters",
        related_clusters=[1, 3, 5],
    )

    with patch("backend.db.database.get_session", return_value=_mock_session_context(db_session)):
        persistence.persist_gaps(_make_result([gap]), db_run_id)

    db_gap = db_session.query(ResearchGapDB).first()
    assert db_gap is not None
    assert db_gap.related_clusters is not None
    parsed = json.loads(db_gap.related_clusters)
    assert parsed == [1, 3, 5]


# ── TEST-38-02-03: persist_cluster_report writes cluster_report_json ─


def test_38_02_03_persist_cluster_report_writes_json(db_session, db_run_id, persistence):
    """persist_cluster_report must write cluster_report_json to PipelineRun."""
    report = ClusterReport(
        clusters=[
            ClusterInfo(cluster_id=0, label="NLP", paper_count=10),
            ClusterInfo(cluster_id=1, label="CV", paper_count=5),
        ],
        total_papers=15,
    )

    with patch("backend.db.database.get_session", return_value=_mock_session_context(db_session)):
        persistence.persist_cluster_report(report, db_run_id)

    db_session.expire_all()
    run = db_session.get(PipelineRun, db_run_id)
    assert run.cluster_report_json is not None
    parsed = json.loads(run.cluster_report_json)
    assert parsed["total_papers"] == 15
    assert len(parsed["clusters"]) == 2
    assert parsed["clusters"][0]["label"] == "NLP"


# ── TEST-38-02-04: load_gaps reconstructs ResearchGap with truth ─────


def test_38_02_04_load_gaps_reconstructs_truth_values(db_session, db_run_id, persistence):
    """load_gaps must reconstruct ResearchGap with TruthValue from DB columns."""
    # Insert a gap with truth data directly
    gap_db = ResearchGapDB(
        title="Reconstruct Test",
        description="Testing reconstruction",
        gap_type="empirical",
        confidence=0.6,
        potential_impact="High",
        pipeline_run_id=db_run_id,
        truth_frequency=0.65,
        truth_confidence=0.80,
        truth_evidence_count=3,
        related_clusters=json.dumps([2, 4]),
    )
    db_session.add(gap_db)
    db_session.commit()

    with patch("backend.db.database.get_session", return_value=_mock_session_context(db_session)):
        gaps = persistence.load_gaps(db_run_id)

    assert len(gaps) == 1
    gap = gaps[0]
    assert gap.title == "Reconstruct Test"
    assert gap.truth.frequency == 0.65
    assert gap.truth.confidence == 0.80
    assert gap.truth.evidence_count == 3
    assert gap.related_clusters == [2, 4]


# ── TEST-38-02-05: Full roundtrip (HB-03) ────────────────────────────


def test_38_02_05_full_roundtrip_persist_load(db_session, db_run_id, persistence):
    """Full roundtrip: persist gaps → load gaps → assert equality (HB-03)."""
    original_gaps = [
        ResearchGap(
            title="Gap Alpha",
            description="First test gap",
            gap_type="methodological",
            confidence=0.9,
            potential_impact="Critical",
            related_clusters=[1, 2, 3],
            truth=TruthValue(frequency=0.88, confidence=0.92, evidence_count=7),
        ),
        ResearchGap(
            title="Gap Beta",
            description="Second test gap",
            gap_type="theoretical",
            confidence=0.7,
            potential_impact="Medium",
            related_clusters=[],
            truth=TruthValue(frequency=0.55, confidence=0.60, evidence_count=2),
        ),
    ]

    # Persist
    with patch("backend.db.database.get_session", return_value=_mock_session_context(db_session)):
        persistence.persist_gaps(_make_result(original_gaps), db_run_id)

    # Load
    with patch("backend.db.database.get_session", return_value=_mock_session_context(db_session)):
        loaded_gaps = persistence.load_gaps(db_run_id)

    # Assert roundtrip fidelity (HB-03)
    assert len(loaded_gaps) == len(original_gaps)

    for orig, loaded in zip(original_gaps, loaded_gaps):
        assert loaded.title == orig.title
        assert loaded.description == orig.description
        assert loaded.gap_type == orig.gap_type
        assert loaded.confidence == orig.confidence
        assert loaded.potential_impact == orig.potential_impact
        # Truth roundtrip
        assert loaded.truth.frequency == orig.truth.frequency
        assert loaded.truth.confidence == orig.truth.confidence
        assert loaded.truth.evidence_count == orig.truth.evidence_count
        # Related clusters roundtrip
        assert loaded.related_clusters == orig.related_clusters
