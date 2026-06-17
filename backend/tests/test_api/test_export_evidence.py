"""Tests for Markdown export with Evidence Trace section.

Phase C: Export Evidence Trace — verifies that exported Markdown
includes source gaps, proposal references, and honest labeling.
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
from backend.db.models import (
    Idea,
    PipelineRun,
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

    app.include_router(router, prefix="/api/v1/export")
    return app


@pytest.fixture
def db_session():
    """In-memory SQLite session (thread-safe for TestClient)."""
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

    import backend.db.database as db_mod
    monkeypatch.setattr(db_mod, "get_session", mock_get_session)
    return TestClient(app)


@pytest.fixture
def run_with_evidence(db_session):
    """Create a run with ideas, gaps, and proposals for evidence trace tests."""
    run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")

    # Create gaps
    gap1 = ResearchGapDB(
        title="Limited cross-domain evaluation",
        description="desc",
        gap_type="empirical",
        confidence=0.85,
        potential_impact="high",
        pipeline_run_id=run.id,
    )
    gap2 = ResearchGapDB(
        title="Inference latency bottleneck",
        description="desc",
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
        source_gap_ids=json.dumps(["Limited cross-domain evaluation", "Inference latency bottleneck"]),
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

    return {"run": run, "idea": idea, "proposal": proposal, "gap1": gap1, "gap2": gap2}


# ── Markdown run export with evidence trace ─────────────────────


class TestMarkdownExportEvidenceTrace:
    """GET /api/v1/export/markdown/{run_id} includes evidence trace."""

    def test_evidence_trace_section_present(self, client, run_with_evidence):
        """Export includes '### Evidence Trace' heading after proposal content."""
        resp = client.get(f"/api/v1/export/markdown/{run_with_evidence['run'].id}")
        assert resp.status_code == 200
        body = resp.text
        assert "### Evidence Trace" in body

    def test_source_gaps_listed_in_export(self, client, run_with_evidence):
        """Resolved source gaps appear in export with type and confidence."""
        resp = client.get(f"/api/v1/export/markdown/{run_with_evidence['run'].id}")
        body = resp.text
        assert "Limited cross-domain evaluation" in body
        assert "Inference latency bottleneck" in body
        assert "[empirical]" in body
        assert "[methodological]" in body
        assert "85% confidence" in body

    def test_proposal_references_in_export(self, client, run_with_evidence):
        """Proposal references appear in export (structured, with match status)."""
        resp = client.get(f"/api/v1/export/markdown/{run_with_evidence['run'].id}")
        body = resp.text
        # Structured references now show parsed titles, not raw strings
        assert "Attention Transfer" in body
        assert "Cross-Domain Eval" in body
        assert "[unresolved]" in body  # No Paper rows to match against

    def test_no_evidence_trace_when_no_data(self, client, db_session):
        """Export omits evidence trace section when idea has no gaps or refs."""
        run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")
        idea = Idea(
            title="Lonely Idea",
            problem_statement="p",
            proposed_method="m",
            expected_contributions="c",
            pipeline_run_id=run.id,
        )
        db_session.add(idea)
        db_session.commit()

        resp = client.get(f"/api/v1/export/markdown/{run.id}")
        body = resp.text
        assert "Evidence Trace" not in body

    def test_unresolved_gaps_marked_honestly(self, client, db_session):
        """Unresolved gap references marked as [unresolved] in export."""
        run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")
        idea = Idea(
            title="Idea with Missing Gap",
            problem_statement="p",
            proposed_method="m",
            expected_contributions="c",
            source_gap_ids=json.dumps(["Nonexistent Gap Title"]),
            pipeline_run_id=run.id,
        )
        db_session.add(idea)
        db_session.commit()

        resp = client.get(f"/api/v1/export/markdown/{run.id}")
        body = resp.text
        assert "[unresolved]" in body
        assert "Nonexistent Gap Title" in body


# ── Bulk Markdown export with evidence trace ─────────────────────


class TestBulkExportEvidenceTrace:
    """POST /api/v1/export/bulk includes evidence trace in Markdown files."""

    def test_bulk_markdown_includes_evidence_trace(self, client, run_with_evidence):
        """Bulk ZIP export includes evidence trace in Markdown output."""
        resp = client.post(
            "/api/v1/export/bulk",
            json={
                "idea_ids": [run_with_evidence["idea"].id],
                "format": "markdown",
            },
        )
        assert resp.status_code == 200

        buffer = BytesIO(resp.content)
        with zipfile.ZipFile(buffer, "r") as zf:
            md_content = zf.read(zf.namelist()[0]).decode("utf-8")
            assert "## Evidence Trace" in md_content
            assert "Limited cross-domain evaluation" in md_content
            # Structured references show parsed titles
            assert "Attention Transfer" in md_content
            assert "[unresolved]" in md_content  # No Paper rows to match
