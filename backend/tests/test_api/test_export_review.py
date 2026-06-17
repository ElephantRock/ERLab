"""Tests for review summary + quality checks in Markdown exports.

Verifies that ensemble review data and deterministic quality checks
appear in both the run-level Markdown export and the bulk ZIP export.
"""

import json
import zipfile
from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.errors import APIError
from backend.api.routes.exports import router
from backend.db import crud
from backend.db.database import Base
from backend.db.models import Idea, PipelineRun, Proposal


def _make_app():
    app = FastAPI()

    @app.exception_handler(APIError)
    async def api_error_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(router, prefix="/api/v1/export")
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


_ENSEMBLE_REVIEW = {
    "overall_score": 0.82,
    "summary": "A strong proposal with sound methodology.",
    "consensus_strengths": ["Rigorous experimental design", "Clear novelty claims"],
    "critical_weaknesses": ["Limited evaluation datasets"],
    "actionable_suggestions": ["Add 3 more baselines"],
    "methodology": None,
    "novelty": None,
    "clarity": None,
}

_SECTIONS_WITH_REVIEW = {
    "abstract": "word " * 160,
    "proposed_method": "word " * 50,  # too short — will fail
    "ensemble_review": _ENSEMBLE_REVIEW,
}


@pytest.fixture
def run_with_review(db_session):
    """Run with a proposal that has ensemble review + incomplete sections."""
    run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")
    idea = Idea(
        title="Reviewed Idea",
        problem_statement="Problem",
        proposed_method="Method",
        expected_contributions="Contributions",
        domain="AI/NLP",
        pipeline_run_id=run.id,
        overall_score=0.8,
    )
    db_session.add(idea)
    db_session.commit()

    proposal = Proposal(
        idea_id=idea.id,
        content_md="# Proposal\n\nContent.",
        references_json=json.dumps([]),
        sections_json=json.dumps(_SECTIONS_WITH_REVIEW),
    )
    db_session.add(proposal)
    db_session.commit()

    return {"run": run, "idea": idea, "proposal": proposal}


@pytest.fixture
def run_without_review(db_session):
    """Run with a proposal that has no ensemble review."""
    run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")
    idea = Idea(
        title="No Review Idea",
        problem_statement="Problem",
        proposed_method="Method",
        expected_contributions="Contributions",
        domain="AI/NLP",
        pipeline_run_id=run.id,
    )
    db_session.add(idea)
    db_session.commit()

    proposal = Proposal(
        idea_id=idea.id,
        content_md="# Proposal\n\nContent.",
        references_json=json.dumps([]),
        sections_json=json.dumps({"abstract": "text"}),
    )
    db_session.add(proposal)
    db_session.commit()

    return {"run": run, "idea": idea}


class TestMarkdownExportReviewSummary:
    """GET /api/v1/export/markdown/{run_id} includes review summary + quality checks."""

    def test_review_summary_section_present(self, client, run_with_review):
        resp = client.get(f"/api/v1/export/markdown/{run_with_review['run'].id}")
        assert resp.status_code == 200
        assert "### Proposal Review" in resp.text

    def test_review_overall_score_in_export(self, client, run_with_review):
        resp = client.get(f"/api/v1/export/markdown/{run_with_review['run'].id}")
        assert "82%" in resp.text

    def test_review_summary_text_in_export(self, client, run_with_review):
        resp = client.get(f"/api/v1/export/markdown/{run_with_review['run'].id}")
        assert "A strong proposal with sound methodology." in resp.text

    def test_review_strengths_in_export(self, client, run_with_review):
        resp = client.get(f"/api/v1/export/markdown/{run_with_review['run'].id}")
        assert "Rigorous experimental design" in resp.text

    def test_review_weaknesses_in_export(self, client, run_with_review):
        resp = client.get(f"/api/v1/export/markdown/{run_with_review['run'].id}")
        assert "Limited evaluation datasets" in resp.text

    def test_quality_checks_section_present(self, client, run_with_review):
        resp = client.get(f"/api/v1/export/markdown/{run_with_review['run'].id}")
        assert "### Quality Checks" in resp.text
        assert "sections passed" in resp.text

    def test_quality_checks_show_failures(self, client, run_with_review):
        """proposed_method has only 50 words (min 600) — should show failure."""
        resp = client.get(f"/api/v1/export/markdown/{run_with_review['run'].id}")
        assert "Proposed Method" in resp.text

    def test_no_review_section_when_absent(self, client, run_without_review):
        resp = client.get(f"/api/v1/export/markdown/{run_without_review['run'].id}")
        assert "Proposal Review" not in resp.text

    def test_quality_checks_still_present_without_review(self, client, run_without_review):
        """Quality checks are independent of ensemble review."""
        resp = client.get(f"/api/v1/export/markdown/{run_without_review['run'].id}")
        assert "Quality Checks" in resp.text


class TestBulkExportReviewSummary:
    """POST /api/v1/export/bulk includes review summary in Markdown files."""

    def test_bulk_markdown_includes_review(self, client, run_with_review):
        resp = client.post(
            "/api/v1/export/bulk",
            json={
                "idea_ids": [run_with_review["idea"].id],
                "format": "markdown",
            },
        )
        assert resp.status_code == 200

        buffer = BytesIO(resp.content)
        with zipfile.ZipFile(buffer, "r") as zf:
            md_content = zf.read(zf.namelist()[0]).decode("utf-8")
            assert "## Proposal Review" in md_content
            assert "82%" in md_content
            assert "A strong proposal" in md_content

    def test_bulk_markdown_includes_quality_checks(self, client, run_with_review):
        resp = client.post(
            "/api/v1/export/bulk",
            json={
                "idea_ids": [run_with_review["idea"].id],
                "format": "markdown",
            },
        )
        assert resp.status_code == 200

        buffer = BytesIO(resp.content)
        with zipfile.ZipFile(buffer, "r") as zf:
            md_content = zf.read(zf.namelist()[0]).decode("utf-8")
            assert "## Quality Checks" in md_content
            assert "sections passed" in md_content

    def test_bulk_markdown_no_review_when_absent(self, client, run_without_review):
        resp = client.post(
            "/api/v1/export/bulk",
            json={
                "idea_ids": [run_without_review["idea"].id],
                "format": "markdown",
            },
        )
        assert resp.status_code == 200

        buffer = BytesIO(resp.content)
        with zipfile.ZipFile(buffer, "r") as zf:
            md_content = zf.read(zf.namelist()[0]).decode("utf-8")
            assert "Proposal Review" not in md_content
