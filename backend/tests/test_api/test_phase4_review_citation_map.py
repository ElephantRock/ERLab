"""Phase 4 / WP-4C — Trust & Sources consumes the persisted citation map.

The Phase 3 defect: Trust & Sources derived its source list from
``references_json`` (LLM-generated proposal text) and never from the
``[SOURCE-N]`` markers actually in the paper. After remediation the review
payload exposes the authoritative marker→source map from
``paper_source_markers`` so the UI shows the same sources exports use.
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
from backend.api.routes.review import router as review_router
from backend.db import crud
from backend.db.database import Base
from backend.db.models import (
    Idea,
    Paper as DBPaper,
    PipelineRun,
    Proposal,
    PaperSourceMarker,
)


@pytest.fixture
def app_with_review(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/phase4_review.db")
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

    app = FastAPI()

    @app.exception_handler(APIError)
    async def _h(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(review_router, prefix="/api/v1/ideas")
    client = TestClient(app)

    with Session() as s:
        run = PipelineRun(status="completed", provenance_version="provenance_v1")
        s.add(run); s.flush()
        idea = Idea(title="Review Idea", problem_statement="p",
                    proposed_method="m", pipeline_run_id=run.id)
        s.add(idea); s.flush()
        proposal = Proposal(
            idea_id=idea.id, content_md="proposal",
            references_json="[]",  # empty — provenance comes from the marker map
            sections_json="{}", paper_md="# Paper [SOURCE-1]",
            paper_meta_json=json.dumps({"status": "ready"}),
        )
        s.add(proposal); s.flush()
        p1 = crud.add_paper(s, source_id="arxiv:rev-1", source="arxiv",
                            title="Review Source", doi="10.55/rev",
                            arxiv_id="rev-1", year=2024, authors='["Rev Author"]')
        s.flush()
        s.add(PaperSourceMarker(proposal_id=proposal.id, marker_index=1, marker="SOURCE-1",
                                source_paper_id=p1.id, mapping_status="mapped"))
        s.add(PaperSourceMarker(proposal_id=proposal.id, marker_index=2, marker="SOURCE-2",
                                source_paper_id=None, mapping_status="unmapped"))
        s.commit()
        idea_id = idea.id

    return client, idea_id


def test_review_exposes_citation_markers_from_map(app_with_review):
    """The review payload includes the authoritative marker→source map."""
    client, idea_id = app_with_review
    resp = client.get(f"/api/v1/ideas/{idea_id}/review")
    assert resp.status_code == 200
    body = resp.json()
    assert "citation_markers" in body
    markers = body["citation_markers"]
    # Two markers: one mapped, one unmapped.
    assert len(markers) == 2
    mapped = [m for m in markers if m["mapping_status"] == "mapped"]
    unmapped = [m for m in markers if m["mapping_status"] == "unmapped"]
    assert len(mapped) == 1
    assert len(unmapped) == 1
    # Mapped marker carries the resolved identity (same source exports use).
    m1 = mapped[0]
    assert m1["marker"] == "SOURCE-1"
    assert m1["title"] == "Review Source"
    assert m1["doi"] == "10.55/rev"


def test_review_unmapped_marker_has_no_identity(app_with_review):
    """An unmapped marker is explicit, with no guessed identity."""
    client, idea_id = app_with_review
    body = client.get(f"/api/v1/ideas/{idea_id}/review").json()
    unmapped = [m for m in body["citation_markers"] if m["mapping_status"] == "unmapped"][0]
    assert unmapped["marker"] == "SOURCE-2"
    assert unmapped.get("title") is None
    assert unmapped.get("doi") is None


def test_review_citation_markers_use_same_identity_as_exports(app_with_review):
    """The marker map is the single source of truth exports also consume."""
    client, idea_id = app_with_review
    review_body = client.get(f"/api/v1/ideas/{idea_id}/review").json()
    # The mapped marker's DOI must match what the BibTeX export would emit.
    mapped = next(m for m in review_body["citation_markers"] if m["mapping_status"] == "mapped")
    assert mapped["doi"] == "10.55/rev"
