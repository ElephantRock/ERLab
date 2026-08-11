"""Phase 4 / WP-4C — exports consume the persisted citation map.

The Phase 3 defect: BibTeX exports contained only self-citations; Markdown/LaTeX
shipped the paper markdown verbatim with no bibliography. These tests pin the
remediation: when a paper has a persisted marker→source map, the exports render
the cited external sources from that map (not from hallucinated references_json
and not as fabricated self-citations).
"""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api.routes.paper_export import router as paper_router
from backend.db import crud
from backend.db.database import Base
from backend.db.models import (
    Idea,
    PaperSourceMarker,
    PipelineRun,
    Proposal,
)


@pytest.fixture
def app_with_mapped_paper(tmp_path, monkeypatch):
    """FastAPI app + a paper that has 2 mapped sources + 1 unmapped marker."""
    engine = create_engine(f"sqlite:///{tmp_path}/phase4_export.db")
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
    app.include_router(paper_router)
    client = TestClient(app)

    with Session() as s:
        run = PipelineRun(status="completed", provenance_version="provenance_v1")
        s.add(run); s.flush()
        idea = Idea(title="Mapped Paper", problem_statement="p",
                    proposed_method="m", pipeline_run_id=run.id)
        s.add(idea); s.flush()
        proposal = Proposal(
            idea_id=idea.id,
            content_md="proposal",
            references_json="[]",  # deliberately empty — provenance comes from the map
            sections_json="{}",
            paper_md="# Paper\n\nCites [SOURCE-1] and [SOURCE-2]; also [SOURCE-99].",
            paper_meta_json=json.dumps({
                "status": "ready", "word_count": 9, "synthesis_strategy": "monolithic",
                "source_map": [
                    {"marker_index": 1, "marker": "SOURCE-1", "source_id": "arxiv:111", "mapping_status": "mapped"},
                    {"marker_index": 2, "marker": "SOURCE-2", "source_id": "arxiv:222", "mapping_status": "mapped"},
                    {"marker_index": 99, "marker": "SOURCE-99", "source_id": None, "mapping_status": "unmapped"},
                ],
            }),
        )
        s.add(proposal); s.flush()
        p1 = crud.add_paper(s, source_id="arxiv:111", source="arxiv",
                            title="Real Source One", doi="10.1/real-one",
                            arxiv_id="111", year=2023, authors='["Alice Author"]')
        p2 = crud.add_paper(s, source_id="arxiv:222", source="arxiv",
                            title="Real Source Two", doi="10.2/real-two",
                            arxiv_id="222", year=2024, authors='["Bob Author"]')
        s.flush()
        s.add(PaperSourceMarker(proposal_id=proposal.id, marker_index=1, marker="SOURCE-1",
                                source_paper_id=p1.id, mapping_status="mapped"))
        s.add(PaperSourceMarker(proposal_id=proposal.id, marker_index=2, marker="SOURCE-2",
                                source_paper_id=p2.id, mapping_status="mapped"))
        s.add(PaperSourceMarker(proposal_id=proposal.id, marker_index=99, marker="SOURCE-99",
                                source_paper_id=None, mapping_status="unmapped"))
        s.commit()
        idea_id = idea.id

    return client, idea_id


class TestBibtexConsumesCitationMap:
    """BibTeX: cited external sources come from the marker map, not self-citations."""

    def test_bibtex_contains_mapped_external_sources(self, app_with_mapped_paper):
        client, idea_id = app_with_mapped_paper
        resp = client.get(f"/paper/bibtex/{idea_id}")
        assert resp.status_code == 200
        body = resp.text
        # Both real sources appear with their DOIs.
        assert "Real Source One" in body
        assert "10.1/real-one" in body
        assert "Real Source Two" in body
        assert "10.2/real-two" in body

    def test_bibtex_still_has_paper_self_entry(self, app_with_mapped_paper):
        client, idea_id = app_with_mapped_paper
        resp = client.get(f"/paper/bibtex/{idea_id}")
        # The paper's own @misc entry is still emitted (so it can be cited).
        assert "@misc{" in resp.text
        assert "Mapped Paper" in resp.text

    def test_bibtex_does_not_fabricate_self_citations_for_sources(self, app_with_mapped_paper):
        """The Phase 3 defect: per-run BibTeX fabricated Paper(source='elephant_rock')
        per source. Per-idea BibTeX must emit the real mapped sources instead."""
        client, idea_id = app_with_mapped_paper
        body = client.get(f"/paper/bibtex/{idea_id}").text
        # The mapped source entries must NOT be elephant_rock self-citations.
        assert "10.1/real-one" in body  # external source present
        # The @article entries (mapped sources) carry real authors, not the
        # platform self-author. The self-author only appears in the @misc entry.
        article_parts = body.split("@article")
        if len(article_parts) > 1:
            # Join all @article entry bodies and assert no platform self-author.
            article_bodies = "@article".join(article_parts[1:])
            assert "Elephant Rock Research Platform" not in article_bodies


class TestMarkdownConsumesCitationMap:
    """Markdown: a bibliography section is rendered from the marker map."""

    def test_markdown_includes_references_section(self, app_with_mapped_paper):
        client, idea_id = app_with_mapped_paper
        body = client.get(f"/paper/markdown/{idea_id}").text
        # The paper body is preserved.
        assert "Cites [SOURCE-1]" in body
        # A references/bibliography section appears with mapped sources.
        assert "Real Source One" in body
        assert "10.1/real-one" in body
        assert "Real Source Two" in body


class TestLatexConsumesCitationMap:
    """LaTeX: a bibliography is rendered from the marker map."""

    def test_latex_includes_bibliography(self, app_with_mapped_paper):
        client, idea_id = app_with_mapped_paper
        body = client.get(f"/paper/latex/{idea_id}").text
        assert "\\documentclass" in body
        # Mapped sources appear in the LaTeX output.
        assert "Real Source One" in body
        assert "10.1/real-one" in body
