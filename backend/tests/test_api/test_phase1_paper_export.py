"""Phase 1 1F focused tests: full-paper export endpoints.

Covers spec 1G backend cases 9–12:
  9.  Markdown export uses paper content.
  10. LaTeX export uses paper content.
  11. BibTeX export uses paper references.
  12. Missing-paper export returns an explicit failure (404).

Uses an in-memory sqlite DB + TestClient against the paper_export router.
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api.routes.paper_export import router as paper_router
from backend.db import crud
from backend.db.database import Base
from backend.db.models import Proposal


@pytest.fixture
def app_with_paper(tmp_path, monkeypatch):
    """Stand up a FastAPI app with the paper_export router backed by a fresh
    in-memory sqlite DB. Patches get_session to use this DB."""
    engine = create_engine(f"sqlite:///{tmp_path}/phase1_paper.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    # Patch the get_session context manager used by paper_export + crud.
    from contextlib import contextmanager

    @contextmanager
    def _test_session():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    # paper_export + crud import get_session lazily inside functions
    # (`from backend.db.database import get_session`), so patching the source
    # module attribute is sufficient — do not patch the importers.
    monkeypatch.setattr("backend.db.database.get_session", _test_session)

    app = FastAPI()
    app.include_router(paper_router)
    client = TestClient(app)

    seed_session = Session()
    try:
        run = crud.create_pipeline_run(seed_session, domain="AI/NLP", status="completed")
        idea = crud.create_idea(
            seed_session,
            title="Test Paper Title",
            problem_statement="p",
            proposed_method="m",
            pipeline_run_id=run.id,
        )
        proposal = Proposal(
            idea_id=idea.id,
            content_md="proposal body",
            references_json="[]",
            sections_json="{}",
            paper_md="# Full Paper\n\nThis is the synthesized full paper body.",
            paper_meta_json=json.dumps(
                {
                    "status": "ready",
                    "word_count": 8,
                    "synthesis_strategy": "monolithic",
                }
            ),
        )
        seed_session.add(proposal)
        seed_session.commit()
        idea_id = idea.id
    finally:
        seed_session.close()

    return client, idea_id


def test_1g_09_markdown_export_uses_paper_content(app_with_paper):
    client, idea_id = app_with_paper
    resp = client.get(f"/paper/markdown/{idea_id}")
    assert resp.status_code == 200
    body = resp.text
    assert "synthesized full paper body" in body
    # Must NOT be the proposal text.
    assert "proposal body" not in body
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert resp.headers["content-disposition"].endswith('.md"')


def test_1g_10_latex_export_uses_paper_content(app_with_paper):
    client, idea_id = app_with_paper
    resp = client.get(f"/paper/latex/{idea_id}")
    assert resp.status_code == 200
    body = resp.text
    assert "\\documentclass" in body
    assert "synthesized full paper body" in body
    assert resp.headers["content-disposition"].endswith('.tex"')


def test_1g_11_bibtex_export_uses_paper_references(app_with_paper):
    client, idea_id = app_with_paper
    resp = client.get(f"/paper/bibtex/{idea_id}")
    assert resp.status_code == 200
    body = resp.text
    # Entry for the paper itself is always emitted.
    assert "@misc{" in body
    assert "Test Paper Title" in body
    assert resp.headers["content-disposition"].endswith('.bib"')


def test_1g_11b_bibtex_includes_resolved_references(app_with_paper, monkeypatch):
    """When the proposal carries resolved references, they appear in the BibTeX."""
    client, idea_id = app_with_paper
    # Add references to the existing proposal via a fresh session.
    from backend.db.database import get_session as _gs  # patched fixture

    with _gs() as session:
        prop = session.query(Proposal).filter_by(idea_id=idea_id).one()
        prop.references_json = json.dumps(
            [
                {"title": "A Referenced Work", "authors": "Doe, J.", "year": 2024, "venue": "Nature"},
            ]
        )
        session.commit()

    resp = client.get(f"/paper/bibtex/{idea_id}")
    assert resp.status_code == 200
    assert "A Referenced Work" in resp.text
    assert "Doe, J." in resp.text


def test_1g_12_missing_paper_returns_explicit_failure(app_with_paper, monkeypatch):
    """Case 12: exporting an idea with no paper returns 404, not fake content."""
    client, _idea_id = app_with_paper
    # Use an idea id that has no proposal/paper.
    missing_id = 99999
    resp = client.get(f"/paper/markdown/{missing_id}")
    assert resp.status_code == 404
    assert "not available" in resp.text.lower()


def test_1g_12b_missing_paper_latex_returns_404(app_with_paper):
    client, _ = app_with_paper
    resp = client.get("/paper/latex/99999")
    assert resp.status_code == 404


def test_1g_12c_missing_paper_bibtex_returns_404(app_with_paper):
    client, _ = app_with_paper
    resp = client.get("/paper/bibtex/99999")
    assert resp.status_code == 404
