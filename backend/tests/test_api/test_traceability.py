"""Tests for traceability resolution: source_gaps, related_ideas, proposal_references.

Phase A: Source Traceability & Evidence UX.
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api.errors import APIError
from backend.api.routes.gaps import router as gaps_router
from backend.api.routes.ideas import router as ideas_router
from backend.db import crud
from backend.db.database import Base
from backend.db.models import (
    Idea,
    Paper,
    Proposal,
    ResearchGapDB,
)

# ── Test app setup ──────────────────────────────────────────────


def _make_app():
    app = FastAPI()

    @app.exception_handler(APIError)
    async def api_error_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(ideas_router, prefix="/ideas")
    app.include_router(gaps_router, prefix="/gaps")
    return app


@pytest.fixture
def db_session():
    """In-memory SQLite session with all tables (thread-safe for TestClient)."""
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def client(monkeypatch, db_session):
    """TestClient with DB session patched."""
    from contextlib import contextmanager

    app = _make_app()

    @contextmanager
    def mock_get_session():
        yield db_session

    # Patch at the source so local imports inside route handlers pick it up
    import backend.db.database as db_mod
    monkeypatch.setattr(db_mod, "get_session", mock_get_session)
    return TestClient(app)


@pytest.fixture
def populated_db(db_session):
    """Create a run with gaps, ideas, proposal, and papers for traceability tests."""
    run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")

    # Create gaps
    gap1 = ResearchGapDB(
        title="Limited cross-domain evaluation",
        description="Most papers only evaluate on single-domain benchmarks.",
        gap_type="empirical",
        confidence=0.85,
        potential_impact="high",
        pipeline_run_id=run.id,
    )
    gap2 = ResearchGapDB(
        title="No real-time inference optimization",
        description="Latency not addressed.",
        gap_type="methodological",
        confidence=0.70,
        potential_impact="medium",
        pipeline_run_id=run.id,
    )
    db_session.add_all([gap1, gap2])
    db_session.commit()

    # Create idea with source_gap_ids referencing gap titles
    idea = Idea(
        title="Cross-Domain Attention Transfer",
        problem_statement="Problem",
        proposed_method="Method",
        expected_contributions="Contributions",
        domain="AI/NLP",
        source_gap_ids=json.dumps(["Limited cross-domain evaluation", "No real-time inference optimization"]),
        pipeline_run_id=run.id,
        overall_score=0.78,
    )
    db_session.add(idea)
    db_session.commit()

    # Create proposal with references
    proposal = Proposal(
        idea_id=idea.id,
        content_md="# Proposal\n\nContent here.",
        references_json=json.dumps([
            {"raw": "Smith et al. (2024). Attention Transfer. NeurIPS."},
            {"raw": "Jones et al. (2023). Cross-Domain Eval. ICML."},
        ]),
        sections_json=json.dumps({}),
    )
    db_session.add(proposal)
    db_session.commit()

    # Create papers
    p1 = Paper(
        source_id="paper-1",
        source="semantic_scholar",
        title="Cross-domain attention mechanisms for NLP",
        abstract="A study on cross-domain attention transfer approaches.",
        authors='["Author A"]',
        year=2024,
        keywords='["attention", "cross-domain"]',
    )
    p2 = Paper(
        source_id="paper-2",
        source="arxiv",
        title="Inference optimization for transformer models",
        abstract="Optimizing transformer inference latency.",
        authors='["Author B"]',
        year=2023,
        keywords='["inference", "optimization"]',
    )
    db_session.add_all([p1, p2])
    db_session.commit()

    return {"run": run, "gap1": gap1, "gap2": gap2, "idea": idea, "proposal": proposal}


# ── Source gaps resolution on idea detail ───────────────────────


class TestSourceGapsResolution:
    """GET /ideas/{id} should resolve source_gap_ids to real gap records."""

    def test_resolved_gaps_have_ids_and_metadata(self, client, populated_db):
        """Source gaps that match real gap titles are fully resolved."""
        resp = client.get(f"/ideas/{populated_db['idea'].id}")
        assert resp.status_code == 200
        source_gaps = resp.json()["idea"]["source_gaps"]
        assert source_gaps is not None
        assert len(source_gaps) == 2

        # First gap: exact title match
        g1 = source_gaps[0]
        assert g1["resolved"] is True
        assert g1["id"] == populated_db["gap1"].id
        assert g1["title"] == "Limited cross-domain evaluation"
        assert g1["gap_type"] == "empirical"
        assert g1["confidence"] == pytest.approx(0.85)

        # Second gap: exact title match
        g2 = source_gaps[1]
        assert g2["resolved"] is True
        assert g2["id"] == populated_db["gap2"].id

    def test_unresolved_gaps_return_raw(self, client, db_session):
        """Unresolvable gap references return {raw, resolved: false}."""
        run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")
        idea = Idea(
            title="Test Idea",
            problem_statement="Problem",
            proposed_method="Method",
            source_gap_ids=json.dumps(["This Gap Does Not Exist"]),
            pipeline_run_id=run.id,
        )
        db_session.add(idea)
        db_session.commit()

        resp = client.get(f"/ideas/{idea.id}")
        assert resp.status_code == 200
        source_gaps = resp.json()["idea"]["source_gaps"]
        assert len(source_gaps) == 1
        assert source_gaps[0]["resolved"] is False
        assert source_gaps[0]["raw"] == "This Gap Does Not Exist"

    def test_normalized_title_match(self, client, db_session):
        """Gaps with different casing/punctuation still resolve."""
        run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")
        gap = ResearchGapDB(
            title="Limited Cross-Domain Evaluation!",
            description="desc",
            gap_type="empirical",
            confidence=0.8,
            pipeline_run_id=run.id,
        )
        db_session.add(gap)
        db_session.commit()

        idea = Idea(
            title="Idea",
            problem_statement="p",
            proposed_method="m",
            source_gap_ids=json.dumps(["limited crossdomain evaluation"]),
            pipeline_run_id=run.id,
        )
        db_session.add(idea)
        db_session.commit()

        resp = client.get(f"/ideas/{idea.id}")
        source_gaps = resp.json()["idea"]["source_gaps"]
        assert len(source_gaps) == 1
        assert source_gaps[0]["resolved"] is True
        assert source_gaps[0]["id"] == gap.id

    def test_mixed_resolved_and_unresolved(self, client, db_session):
        """A mix of resolvable and unresolvable references."""
        run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")
        gap = ResearchGapDB(
            title="Real Gap",
            description="d",
            gap_type="theoretical",
            confidence=0.9,
            pipeline_run_id=run.id,
        )
        db_session.add(gap)
        db_session.commit()

        idea = Idea(
            title="Idea X",
            problem_statement="p",
            proposed_method="m",
            source_gap_ids=json.dumps(["Real Gap", "Fake Gap"]),
            pipeline_run_id=run.id,
        )
        db_session.add(idea)
        db_session.commit()

        resp = client.get(f"/ideas/{idea.id}")
        source_gaps = resp.json()["idea"]["source_gaps"]
        assert len(source_gaps) == 2
        assert source_gaps[0]["resolved"] is True
        assert source_gaps[1]["resolved"] is False

    def test_no_source_gaps_returns_null(self, client, db_session):
        """Idea with no source_gap_ids returns null for source_gaps."""
        run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")
        idea = Idea(
            title="Lonely Idea",
            problem_statement="p",
            proposed_method="m",
            source_gap_ids=None,
            pipeline_run_id=run.id,
        )
        db_session.add(idea)
        db_session.commit()

        resp = client.get(f"/ideas/{idea.id}")
        assert resp.json()["idea"]["source_gaps"] is None
        assert resp.json()["idea"]["source_gap_ids"] is None


# ── Proposal references on idea detail ──────────────────────────


class TestProposalReferences:
    """GET /ideas/{id} should include structured proposal references."""

    def test_references_present(self, client, populated_db):
        """Proposal references are returned as a list of {raw} dicts."""
        resp = client.get(f"/ideas/{populated_db['idea'].id}")
        refs = resp.json()["idea"]["proposal_references"]
        assert refs is not None
        assert len(refs) == 2
        assert "Smith et al." in refs[0]["raw"]

    def test_no_proposal_returns_null_references(self, client, db_session):
        """Idea without a proposal returns null for proposal_references."""
        run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")
        idea = Idea(
            title="No Proposal Idea",
            problem_statement="p",
            proposed_method="m",
            pipeline_run_id=run.id,
        )
        db_session.add(idea)
        db_session.commit()

        resp = client.get(f"/ideas/{idea.id}")
        assert resp.json()["idea"]["proposal_references"] is None


# ── Related ideas on gap detail ──────────────────────────────────


class TestRelatedIdeas:
    """GET /gaps/{id} should include related ideas that reference this gap."""

    def test_related_ideas_present(self, client, populated_db):
        """Gap detail includes ideas whose source_gap_ids reference it."""
        resp = client.get(f"/gaps/{populated_db['gap1'].id}")
        assert resp.status_code == 200
        related = resp.json()["gap"]["related_ideas"]
        assert related is not None
        assert len(related) == 1
        assert related[0]["title"] == "Cross-Domain Attention Transfer"
        assert related[0]["overall_score"] == pytest.approx(0.78)

    def test_no_related_ideas_returns_null(self, client, db_session):
        """Gap with no ideas referencing it returns null."""
        run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")
        gap = ResearchGapDB(
            title="Lonely Gap",
            description="d",
            gap_type="empirical",
            confidence=0.5,
            pipeline_run_id=run.id,
        )
        db_session.add(gap)
        db_session.commit()

        resp = client.get(f"/gaps/{gap.id}")
        assert resp.json()["gap"]["related_ideas"] is None


# ── Matched papers preview on gap detail ────────────────────────


class TestMatchedPapersPreview:
    """GET /gaps/{id} should include top-5 keyword-matched papers."""

    def test_matched_papers_present(self, client, populated_db):
        """Gap detail includes matched_papers_preview with top matches."""
        resp = client.get(f"/gaps/{populated_db['gap1'].id}")
        assert resp.status_code == 200
        preview = resp.json()["gap"]["matched_papers_preview"]
        assert preview is not None
        assert len(preview) <= 5
        # Paper about cross-domain attention should match gap about cross-domain eval
        titles = [p["title"] for p in preview]
        assert any("cross-domain" in t.lower() for t in titles)

    def test_preview_has_core_fields(self, client, populated_db):
        """Each matched paper has id, title, abstract, year, venue, citation_count."""
        resp = client.get(f"/gaps/{populated_db['gap1'].id}")
        preview = resp.json()["gap"]["matched_papers_preview"]
        assert preview is not None
        p = preview[0]
        assert "id" in p
        assert "title" in p
        assert "year" in p
        assert "citation_count" in p

    def test_no_matching_papers_returns_null(self, client, db_session):
        """Gap with no keyword matches returns null."""
        run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")
        gap = ResearchGapDB(
            title="ZZZ Unmatched Topic",
            description="d",
            gap_type="empirical",
            confidence=0.5,
            pipeline_run_id=run.id,
        )
        db_session.add(gap)
        db_session.commit()

        resp = client.get(f"/gaps/{gap.id}")
        assert resp.json()["gap"]["matched_papers_preview"] is None
