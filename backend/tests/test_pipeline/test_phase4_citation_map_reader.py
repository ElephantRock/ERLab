"""Phase 4 / WP-4C tests — citation-map reader (single read-path for consumers).

Exports (Markdown/LaTeX/BibTeX) and Trust & Sources must all consume the SAME
persisted marker map. This test pins the shared reader that loads the citation
map for a proposal and exposes resolved bibliographic identity per marker.
"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db import crud
from backend.db.database import Base
from backend.db.models import (
    Idea,
    PaperSourceMarker,
    PipelineRun,
    Proposal,
)


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/cm.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        yield s


def _seed_paper_with_markers(session) -> tuple[int, int]:
    """Seed run→idea→proposal + 2 papers + 2 mapped markers + 1 unmapped."""
    run = PipelineRun(status="completed", provenance_version="provenance_v1")
    session.add(run); session.flush()
    idea = Idea(title="T", problem_statement="p", proposed_method="m", pipeline_run_id=run.id)
    session.add(idea); session.flush()
    proposal = Proposal(
        idea_id=idea.id, content_md="# P",
        paper_md="# Paper citing [SOURCE-1] and [SOURCE-2].",
        paper_meta_json=json.dumps({"status": "ready", "source_count": 2}),
    )
    session.add(proposal); session.flush()
    p1 = crud.add_paper(session, source_id="arxiv:111", source="arxiv",
                        title="Source One", doi="10.1/aaa", arxiv_id="111", year=2023,
                        authors='["Alice A."]')  # authors stored as JSON string
    p2 = crud.add_paper(session, source_id="arxiv:222", source="arxiv",
                        title="Source Two", doi="10.2/bbb", arxiv_id="222", year=2024)
    session.flush()
    session.add(PaperSourceMarker(proposal_id=proposal.id, marker_index=1, marker="SOURCE-1",
                                  source_paper_id=p1.id, mapping_status="mapped"))
    session.add(PaperSourceMarker(proposal_id=proposal.id, marker_index=2, marker="SOURCE-2",
                                  source_paper_id=p2.id, mapping_status="mapped"))
    session.add(PaperSourceMarker(proposal_id=proposal.id, marker_index=99, marker="SOURCE-99",
                                  source_paper_id=None, mapping_status="unmapped"))
    session.commit()
    return proposal.id, idea.id


class TestCitationMapReader:
    """The shared reader that exports + Trust & Sources consume."""

    def test_loads_mapped_markers_with_identity(self, db_session):
        from backend.pipeline.provenance.citation_map import load_citation_map

        proposal_id, _ = _seed_paper_with_markers(db_session)
        entries = load_citation_map(db_session, proposal_id)

        # Two mapped + one unmapped.
        mapped = [e for e in entries if e.mapping_status == "mapped"]
        unmapped = [e for e in entries if e.mapping_status == "unmapped"]
        assert len(mapped) == 2
        assert len(unmapped) == 1

        # Mapped entries carry the resolved Paper identity.
        e1 = next(e for e in entries if e.marker == "SOURCE-1")
        assert e1.source_paper is not None
        assert e1.source_paper.doi == "10.1/aaa"
        assert e1.source_paper.arxiv_id == "111"
        assert e1.source_paper.title == "Source One"

    def test_unmapped_marker_carries_no_identity(self, db_session):
        from backend.pipeline.provenance.citation_map import load_citation_map

        proposal_id, _ = _seed_paper_with_markers(db_session)
        entries = load_citation_map(db_session, proposal_id)

        e99 = next(e for e in entries if e.marker == "SOURCE-99")
        assert e99.mapping_status == "unmapped"
        assert e99.source_paper is None
        assert e99.source_paper_id is None

    def test_empty_for_proposal_without_markers(self, db_session):
        from backend.pipeline.provenance.citation_map import load_citation_map

        run = PipelineRun(status="completed", provenance_version="provenance_v1")
        db_session.add(run); db_session.flush()
        idea = Idea(title="X", problem_statement="p", proposed_method="m", pipeline_run_id=run.id)
        db_session.add(idea); db_session.flush()
        proposal = Proposal(idea_id=idea.id, content_md="# P")
        db_session.add(proposal); db_session.commit()

        entries = load_citation_map(db_session, proposal.id)
        assert entries == []

    def test_entries_ordered_by_marker_index(self, db_session):
        from backend.pipeline.provenance.citation_map import load_citation_map

        proposal_id, _ = _seed_paper_with_markers(db_session)
        entries = load_citation_map(db_session, proposal_id)
        # 1, 2, then 99 (unmapped sorts after mapped by index).
        assert [e.marker_index for e in entries] == [1, 2, 99]
