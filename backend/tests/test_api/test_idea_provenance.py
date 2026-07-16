"""Tests for the get_idea API returning supporting papers and structured refs."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.errors import APIError
from backend.api.routes.ideas import router
from backend.db import crud
from backend.db.database import Base
from backend.db.models import Idea, IdeaPaperLink, Paper, PipelineRun, Proposal


def _make_app():
    app = FastAPI()

    @app.exception_handler(APIError)
    async def api_error_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(router, prefix="/api/v1/ideas")
    return app


@pytest.fixture
def db_session():
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
    from contextlib import contextmanager

    app = _make_app()

    @contextmanager
    def mock_get_session():
        yield db_session

    import backend.db.database as db_mod
    monkeypatch.setattr(db_mod, "get_session", mock_get_session)
    return TestClient(app)


@pytest.fixture
def idea_with_papers(db_session):
    """Create an idea with linked papers and a proposal with references."""
    run = PipelineRun(domain="AI/NLP", status="completed",
                      provenance_version="pre_provenance",
                      legacy_provenance_reason="pre_gating_run")
    db_session.add(run)
    db_session.commit()

    paper1 = Paper(
        source_id="sse-001", source="semantic_scholar",
        title="Attention Transfer Mechanism",
        year=2024, venue="NeurIPS", citation_count=42,
        doi="10.1234/attn", arxiv_id=None,
    )
    paper2 = Paper(
        source_id="arxiv-002", source="arxiv",
        title="Cross-Domain Evaluation Methods",
        year=2023, venue="ICML", citation_count=15,
        doi=None, arxiv_id="2301.99999",
    )
    db_session.add_all([paper1, paper2])
    db_session.commit()

    idea = Idea(
        title="Test Idea",
        problem_statement="Problem",
        proposed_method="Method",
        expected_contributions="Contrib",
        pipeline_run_id=run.id,
    )
    db_session.add(idea)
    db_session.commit()

    # Link papers to idea
    db_session.add_all([
        IdeaPaperLink(idea_id=idea.id, paper_id=paper1.id, role="supporting"),
        IdeaPaperLink(idea_id=idea.id, paper_id=paper2.id, role="supporting"),
    ])
    db_session.commit()

    # Create proposal with references that will match
    proposal = Proposal(
        idea_id=idea.id,
        content_md="# Proposal\n\nContent.",
        references_json=json.dumps([
            {"raw": "[1] Smith (2024). Attention Transfer Mechanism. NeurIPS. DOI: 10.1234/attn."},
            {"raw": "[2] Jones (2023). Some Unmatched Paper."},
        ]),
        sections_json=json.dumps({"abstract": "text"}),
    )
    db_session.add(proposal)
    db_session.commit()

    return {"idea": idea, "papers": [paper1, paper2], "proposal": proposal, "run": run}


class TestGetIdeaSupportingPapers:
    def test_supporting_papers_returned(self, client, idea_with_papers):
        idea_id = idea_with_papers["idea"].id
        resp = client.get(f"/api/v1/ideas/{idea_id}")
        assert resp.status_code == 200

        data = resp.json()["idea"]
        assert data["supporting_papers"] is not None
        assert len(data["supporting_papers"]) == 2

    def test_supporting_paper_fields(self, client, idea_with_papers):
        idea_id = idea_with_papers["idea"].id
        resp = client.get(f"/api/v1/ideas/{idea_id}")
        papers = resp.json()["idea"]["supporting_papers"]

        p1 = next(p for p in papers if p["title"] == "Attention Transfer Mechanism")
        assert p1["year"] == 2024
        assert p1["venue"] == "NeurIPS"
        assert p1["citation_count"] == 42
        assert p1["doi"] == "10.1234/attn"
        assert p1["role"] == "supporting"

    def test_no_supporting_papers_returns_null(self, client, db_session):
        """Idea without paper links should have null supporting_papers."""
        run = PipelineRun(domain="AI/NLP", status="completed",
                      provenance_version="pre_provenance",
                      legacy_provenance_reason="pre_gating_run")
        db_session.add(run)
        db_session.commit()

        idea = Idea(
            title="Lonely Idea",
            problem_statement="p", proposed_method="m",
            expected_contributions="c", pipeline_run_id=run.id,
        )
        db_session.add(idea)
        db_session.commit()

        resp = client.get(f"/api/v1/ideas/{idea.id}")
        assert resp.status_code == 200
        assert resp.json()["idea"]["supporting_papers"] is None


class TestGetIdeaStructuredReferences:
    def test_references_are_structured(self, client, idea_with_papers):
        """Proposal references should be structured with resolved/match fields."""
        idea_id = idea_with_papers["idea"].id
        resp = client.get(f"/api/v1/ideas/{idea_id}")
        refs = resp.json()["idea"]["proposal_references"]

        assert isinstance(refs, list)
        assert len(refs) == 2

    def test_resolved_reference_has_paper(self, client, idea_with_papers):
        """Reference matching a Paper should have resolved=true and paper data."""
        idea_id = idea_with_papers["idea"].id
        resp = client.get(f"/api/v1/ideas/{idea_id}")
        refs = resp.json()["idea"]["proposal_references"]

        resolved = [r for r in refs if r["resolved"]]
        assert len(resolved) == 1
        assert resolved[0]["paper"] is not None
        assert resolved[0]["paper"]["title"] == "Attention Transfer Mechanism"
        assert resolved[0]["match_method"] == "doi"
        assert resolved[0]["match_confidence"] == 1.0

    def test_unresolved_reference_preserved(self, client, idea_with_papers):
        """Unresolved references should still appear with raw text."""
        idea_id = idea_with_papers["idea"].id
        resp = client.get(f"/api/v1/ideas/{idea_id}")
        refs = resp.json()["idea"]["proposal_references"]

        unresolved = [r for r in refs if not r["resolved"]]
        assert len(unresolved) == 1
        assert unresolved[0]["paper"] is None
        assert unresolved[0]["resolved"] is False
        assert "Some Unmatched Paper" in unresolved[0]["raw"]

    def test_references_include_raw_always(self, client, idea_with_papers):
        """Every reference must preserve the raw string."""
        idea_id = idea_with_papers["idea"].id
        resp = client.get(f"/api/v1/ideas/{idea_id}")
        refs = resp.json()["idea"]["proposal_references"]

        for ref in refs:
            assert ref["raw"]
            assert isinstance(ref["raw"], str)

    def test_null_references_when_no_proposal(self, client, db_session):
        """Idea without a proposal should have null references."""
        run = PipelineRun(domain="AI/NLP", status="completed",
                      provenance_version="pre_provenance",
                      legacy_provenance_reason="pre_gating_run")
        db_session.add(run)
        db_session.commit()

        idea = Idea(
            title="No Proposal Idea",
            problem_statement="p", proposed_method="m",
            expected_contributions="c", pipeline_run_id=run.id,
        )
        db_session.add(idea)
        db_session.commit()

        resp = client.get(f"/api/v1/ideas/{idea.id}")
        assert resp.status_code == 200
        assert resp.json()["idea"]["proposal_references"] is None
