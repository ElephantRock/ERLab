"""Regression (run 2712): autonomous_experiment_design must survive the
_extract_paper_artifact schema boundary on every path that persists
metadata. Runs 2710-2712 lost the key at this boundary, so cold
/paper/repair could never recover the autonomous design from the DB.

Tests the extractor directly (ready / failed / empty-markdown /
not-selected / absent) and the full DB round-trip through
persist_proposals() — the exact boundary that failed in production.
"""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.database as db_mod
from backend.db.database import Base
from backend.db.models import Idea, PipelineRun, Proposal
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.persistence import PipelinePersistence, _extract_paper_artifact
from backend.pipeline.result import PipelineResult

DESIGN = {
    "status": "designed",
    "capability": "tabular_calibration_selective_v1",
    "selected_proposal_idx": 0,
    "specs": [
        {"spec_id": "auto/calibration/iris", "dataset": "iris"},
        {"spec_id": "auto/calibration/wine", "dataset": "wine_quality"},
    ],
}

READY_FULL_PAPER = {
    "paper_markdown": "## Title\n\nEmpirical study.\n\nAccuracy was 0.93 [RESULT-1].",
    "word_count": 6,
    "venue": "Generic",
    "model_used": "unknown",
    "source_count": 3,
    "sections_generated": 6,
    "sections_total": 6,
    "synthesis_strategy": "sectioned",
    "source_map": [],
}


def _proposal(metadata: dict) -> SimpleNamespace:
    return SimpleNamespace(metadata=json.dumps(metadata))


# ── Extractor: ready path ───────────────────────────────────────────────────


class TestReadyPath:
    def test_ready_path_preserves_design(self):
        proposal = _proposal({
            "full_paper": dict(READY_FULL_PAPER),
            "autonomous_experiment_design": DESIGN,
        })
        paper_md, meta = _extract_paper_artifact(proposal)
        assert paper_md is not None
        assert meta["status"] == "ready"
        assert meta["autonomous_experiment_design"] == DESIGN

    def test_ready_path_design_is_exact_object(self):
        design = {
            "status": "designed",
            "specs": [
                {"spec_id": "s1", "dataset": "iris", "metrics": ["a", "b"]},
            ],
            "extra_nested": {"x": [1, 2, {"y": None}]},
        }
        proposal = _proposal({
            "full_paper": dict(READY_FULL_PAPER),
            "autonomous_experiment_design": design,
        })
        _, meta = _extract_paper_artifact(proposal)
        assert meta["autonomous_experiment_design"] == design


# ── Extractor: failed paths (the cold-repair case) ─────────────────────────


class TestFailedPaths:
    def test_none_full_paper_preserves_design(self):
        proposal = _proposal({
            "full_paper": None,
            "synthesis_state": "timeout",
            "autonomous_experiment_design": DESIGN,
        })
        paper_md, meta = _extract_paper_artifact(proposal)
        assert paper_md is None
        assert meta["status"] == "failed"
        assert meta["autonomous_experiment_design"] == DESIGN

    def test_empty_markdown_preserves_design(self):
        proposal = _proposal({
            "full_paper": {"paper_markdown": "   "},
            "autonomous_experiment_design": DESIGN,
        })
        _, meta = _extract_paper_artifact(proposal)
        assert meta["status"] == "failed"
        assert meta["autonomous_experiment_design"] == DESIGN

    def test_non_dict_full_paper_preserves_design(self):
        proposal = _proposal({
            "full_paper": "garbage",
            "autonomous_experiment_design": DESIGN,
        })
        _, meta = _extract_paper_artifact(proposal)
        assert meta["status"] == "failed"
        assert meta["autonomous_experiment_design"] == DESIGN

    def test_not_selected_preserves_design(self):
        proposal = _proposal({
            "experiment_status": "not_selected_for_experiment",
            "autonomous_experiment_design": DESIGN,
        })
        _, meta = _extract_paper_artifact(proposal)
        assert meta["status"] == "not_requested"
        assert meta["autonomous_experiment_design"] == DESIGN


# ── Extractor: no design → shape unchanged ─────────────────────────────────


class TestAbsentDesign:
    def test_ready_meta_shape_unchanged(self):
        proposal = _proposal({"full_paper": dict(READY_FULL_PAPER)})
        _, meta = _extract_paper_artifact(proposal)
        assert "autonomous_experiment_design" not in meta
        assert meta["status"] == "ready"

    def test_failed_meta_shape_unchanged(self):
        proposal = _proposal({"full_paper": None})
        _, meta = _extract_paper_artifact(proposal)
        assert meta == {"status": "failed", "generated_at": None}

    def test_no_paper_stage_still_returns_none_none(self):
        proposal = _proposal({})
        paper_md, meta = _extract_paper_artifact(proposal)
        assert paper_md is None
        assert meta is None


# ── DB round-trip through persist_proposals (production boundary) ──────────


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _fk(conn, record):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    return engine


def _seed_run_and_idea(engine) -> tuple[int, int]:
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    run = PipelineRun(
        run_id_str="run_pr9b", domain="ML", status="running",
        config_json="{}", stages_completed="[]",
        provenance_version="provenance_v1",
    )
    session.add(run)
    session.commit()
    idea = Idea(
        title="Calibration Study",
        problem_statement="Calibration under shift",
        proposed_method="Temperature scaling",
        expected_contributions="Better selective classification",
        domain="ML", novelty_score=0.5, feasibility_score=0.8,
        overall_score=0.8, pipeline_run_id=run.id,
    )
    session.add(idea)
    session.commit()
    ids = (run.id, idea.id)
    session.close()
    return ids


def _run_result_with_proposal(metadata: dict) -> PipelineResult:
    result = PipelineResult()
    result.ideas = [ResearchIdea(
        title="Calibration Study",
        problem_statement="Calibration under shift",
        proposed_method="Temperature scaling",
        expected_contributions="Better selective classification",
        novelty_rationale="Novel", evaluation_approach="metrics",
        domain="ML", round_generated=1, score=0.8,
        supporting_papers=[], source_gap_ids=[],
    )]
    result.proposals = {0: SimpleNamespace(
        metadata=json.dumps(metadata),
        sections={"references": []},
        to_markdown=lambda: "## Title\n\nProposal body",
    )}
    return result


class TestPersistProposalsRoundTrip:
    def test_ready_paper_design_reaches_db(self):
        engine = _make_engine()
        run_id, _ = _seed_run_and_idea(engine)
        test_sf = sessionmaker(bind=engine, expire_on_commit=False)

        import contextlib

        @contextlib.contextmanager
        def patched_session():
            session = test_sf()
            try:
                yield session
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        orig = db_mod.get_session
        db_mod.get_session = patched_session
        try:
            result = _run_result_with_proposal({
                "full_paper": dict(READY_FULL_PAPER),
                "autonomous_experiment_design": DESIGN,
            })
            PipelinePersistence().persist_proposals(result, run_id)
        finally:
            db_mod.get_session = orig

        session = test_sf()
        row = session.execute(select(Proposal)).scalar_one()
        session.close()

        persisted = json.loads(row.paper_meta_json)
        assert persisted["status"] == "ready"
        assert persisted["autonomous_experiment_design"] == DESIGN

    def test_failed_paper_design_reaches_db(self):
        """The production cold-repair case: paper blocked/failed, design
        state must still be queryable from paper_meta_json."""
        engine = _make_engine()
        run_id, _ = _seed_run_and_idea(engine)
        test_sf = sessionmaker(bind=engine, expire_on_commit=False)

        import contextlib

        @contextlib.contextmanager
        def patched_session():
            session = test_sf()
            try:
                yield session
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        orig = db_mod.get_session
        db_mod.get_session = patched_session
        try:
            result = _run_result_with_proposal({
                "full_paper": None,
                "synthesis_state": "timeout",
                "autonomous_experiment_design": DESIGN,
            })
            PipelinePersistence().persist_proposals(result, run_id)
        finally:
            db_mod.get_session = orig

        session = test_sf()
        row = session.execute(select(Proposal)).scalar_one()
        session.close()

        assert row.paper_md is None
        persisted = json.loads(row.paper_meta_json)
        assert persisted["status"] == "failed"
        assert persisted["autonomous_experiment_design"] == DESIGN
