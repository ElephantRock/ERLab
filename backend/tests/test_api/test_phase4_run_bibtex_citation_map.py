"""Phase 4 / WP-4C — per-run BibTeX consumes the persisted citation map.

The Phase 3 defect (boundary 12 in PHASE_4_SOURCE_PROVENANCE_TRACE.md):
``export_run_bibtex`` fabricated a self-citation ``Paper(source='elephant_rock')``
per idea and never read the ``papers`` table, producing "only self-citations"
output. This test pins the remediation: a run whose proposals have marker maps
emits the cited external sources.
"""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api.errors import APIError
from backend.api.routes.exports import router
from backend.db import crud
from backend.db.database import Base
from backend.db.models import (
    Idea,
    Paper as DBPaper,
    PipelineRun,
    Proposal,
    PaperSourceMarker,
)


def _make_app():
    app = FastAPI()

    @app.exception_handler(APIError)
    async def _h(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(router, prefix="/api/v1/export")
    return app


@pytest.fixture
def app_with_run(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/run_bib.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _test_session():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    monkeypatch.setattr("backend.db.database.get_session", _test_session)

    app = _make_app()
    client = TestClient(app)

    with Session() as s:
        run = PipelineRun(status="completed", provenance_version="provenance_v1")
        s.add(run); s.flush()
        idea = Idea(title="Run Idea", problem_statement="p",
                    proposed_method="m", pipeline_run_id=run.id)
        s.add(idea); s.flush()
        proposal = Proposal(
            idea_id=idea.id, content_md="proposal", references_json="[]", sections_json="{}",
            paper_md="# Paper [SOURCE-1]",
            paper_meta_json=json.dumps({"status": "ready"}),
        )
        s.add(proposal); s.flush()
        p1 = crud.add_paper(s, source_id="arxiv:run-1", source="arxiv",
                            title="Run External Source", doi="10.99/run-source",
                            arxiv_id="run-1", year=2024, authors='["Carol Cite"]')
        s.flush()
        s.add(PaperSourceMarker(proposal_id=proposal.id, marker_index=1, marker="SOURCE-1",
                                source_paper_id=p1.id, mapping_status="mapped"))
        s.commit()
        run_id = run.id

    return client, run_id


def test_run_bibtex_emits_mapped_external_sources(app_with_run):
    """Per-run BibTeX includes the cited external sources from the marker map."""
    client, run_id = app_with_run
    resp = client.get(f"/api/v1/export/bibtex/{run_id}")
    assert resp.status_code == 200
    body = resp.text
    assert "Run External Source" in body
    assert "10.99/run-source" in body
    assert "Carol Cite" in body


def test_run_bibtex_no_longer_fabricates_only_self_citations(app_with_run):
    """The Phase 3 defect: every entry was an elephant_rock self-citation.

    After remediation the run's external sources appear, so the output is not
    ONLY self-citations."""
    client, run_id = app_with_run
    body = client.get(f"/api/v1/export/bibtex/{run_id}").text
    # External source present (not just self-citations).
    assert "10.99/run-source" in body
    # The @article entries (external) do not carry the platform self-author.
    if "@article" in body:
        article_bodies = body.split("@article", 1)[1]
        assert "Elephant Rock" not in article_bodies
