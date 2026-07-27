"""Phase 4 / WP-4B tests — paper source-marker provenance table.

These tests pin the durable marker-to-source mapping that today is lost at the
synthesis boundary (see docs/project/phase4/PHASE_4_SOURCE_PROVENANCE_TRACE.md).

The marker table is the smallest run-scoped source manifest: for each generated
paper, one row per cited source carrying the literal `[SOURCE-N]` marker and a
link back to the persistent `papers` row (or an explicit `unmapped` state).
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.db.models import Base, Idea, Paper, PipelineRun, Proposal, PaperSourceMarker
from backend.db import crud


@pytest.fixture
def session():
    """Fresh in-memory SQLite session with all tables created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


def _make_proposal(session: Session) -> Proposal:
    """Insert a minimal run → idea → proposal chain and return the proposal."""
    run = PipelineRun(
        status="completed",
        provenance_version="provenance_v1",
    )
    session.add(run)
    session.flush()
    idea = Idea(
        title="Test Idea",
        problem_statement="p",
        proposed_method="m",
        pipeline_run_id=run.id,
    )
    session.add(idea)
    session.flush()
    proposal = Proposal(idea_id=idea.id, content_md="# Test proposal")
    session.add(proposal)
    session.flush()
    return proposal


def _make_paper(session: Session, *, source_id: str = "arxiv:2401.00001", doi: str | None = "10.1000/test") -> Paper:
    paper = crud.add_paper(
        session,
        source_id=source_id,
        source="arxiv",
        title="Cited Source Paper",
        doi=doi,
        arxiv_id="2401.00001",
        year=2024,
    )
    session.flush()
    return paper


class TestPaperSourceMarkerModel:
    """Schema and constraint behavior of the paper_source_markers table."""

    def test_marker_persists_mapped_source(self, session):
        """A marker linked to a paper round-trips through the DB."""
        proposal = _make_proposal(session)
        paper = _make_paper(session)

        marker = PaperSourceMarker(
            proposal_id=proposal.id,
            marker_index=1,
            marker="SOURCE-1",
            source_paper_id=paper.id,
            mapping_status="mapped",
        )
        session.add(marker)
        session.commit()

        loaded = session.get(PaperSourceMarker, marker.id)
        assert loaded is not None
        assert loaded.marker == "SOURCE-1"
        assert loaded.marker_index == 1
        assert loaded.source_paper_id == paper.id
        assert loaded.mapping_status == "mapped"
        assert loaded.proposal_id == proposal.id
        assert loaded.created_at is not None

    def test_marker_supports_unmapped_state(self, session):
        """An unmapped marker has a null source_paper_id and explicit status."""
        proposal = _make_proposal(session)

        marker = PaperSourceMarker(
            proposal_id=proposal.id,
            marker_index=99,
            marker="SOURCE-99",
            source_paper_id=None,
            mapping_status="unmapped",
        )
        session.add(marker)
        session.commit()

        loaded = session.get(PaperSourceMarker, marker.id)
        assert loaded.source_paper_id is None
        assert loaded.mapping_status == "unmapped"

    def test_unique_constraint_proposal_marker_index(self, session):
        """UNIQUE (proposal_id, marker_index) — duplicate insert raises."""
        proposal = _make_proposal(session)
        paper = _make_paper(session)

        session.add(PaperSourceMarker(
            proposal_id=proposal.id, marker_index=1, marker="SOURCE-1",
            source_paper_id=paper.id, mapping_status="mapped",
        ))
        session.flush()

        with pytest.raises(IntegrityError):
            session.add(PaperSourceMarker(
                proposal_id=proposal.id, marker_index=1, marker="SOURCE-1-dup",
                source_paper_id=paper.id, mapping_status="mapped",
            ))
            session.flush()

    def test_different_proposals_can_share_marker_index(self, session):
        """The same marker index is legal across different proposals."""
        p1 = _make_proposal(session)
        # second proposal needs a second idea
        idea2 = Idea(title="I2", problem_statement="p", proposed_method="m",
                     pipeline_run_id=p1.idea.pipeline_run_id)
        session.add(idea2)
        session.flush()
        p2 = Proposal(idea_id=idea2.id, content_md="# P2")
        session.add(p2)
        session.flush()
        paper = _make_paper(session)

        session.add(PaperSourceMarker(
            proposal_id=p1.id, marker_index=1, marker="SOURCE-1",
            source_paper_id=paper.id, mapping_status="mapped",
        ))
        session.add(PaperSourceMarker(
            proposal_id=p2.id, marker_index=1, marker="SOURCE-1",
            source_paper_id=paper.id, mapping_status="mapped",
        ))
        session.commit()  # should not raise


class TestPaperSourceMarkerCRUD:
    """CRUD helpers for reading the marker map back."""

    def test_get_markers_for_proposal_returns_ordered(self, session):
        proposal = _make_proposal(session)
        paper = _make_paper(session)
        for idx in [3, 1, 2]:
            session.add(PaperSourceMarker(
                proposal_id=proposal.id, marker_index=idx, marker=f"SOURCE-{idx}",
                source_paper_id=paper.id, mapping_status="mapped",
            ))
        session.commit()

        markers = crud.get_source_markers_for_proposal(session, proposal.id)
        assert [m.marker_index for m in markers] == [1, 2, 3]
        assert all(m.mapping_status == "mapped" for m in markers)

    def test_get_markers_joins_to_paper_identity(self, session):
        """The CRUD helper exposes the linked paper's stable identifiers."""
        proposal = _make_proposal(session)
        paper = _make_paper(session, source_id="arxiv:2401.00002", doi="10.2000/real")
        session.add(PaperSourceMarker(
            proposal_id=proposal.id, marker_index=1, marker="SOURCE-1",
            source_paper_id=paper.id, mapping_status="mapped",
        ))
        session.commit()

        markers = crud.get_source_markers_for_proposal(session, proposal.id)
        assert len(markers) == 1
        m = markers[0]
        # The linked paper carries the stable identity.
        assert m.source_paper is not None
        assert m.source_paper.doi == "10.2000/real"
        assert m.source_paper.arxiv_id == "2401.00001"
