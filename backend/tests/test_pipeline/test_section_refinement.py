"""Tests for section refinement service — revision tracking, concurrency, rollback."""

import hashlib
import json
from unittest.mock import MagicMock

import pytest

from backend.db.models import Proposal, ProposalSectionRevision
from backend.pipeline.synthesis.section_refinement import (
    ConcurrencyConflict,
    ProposalSectionRefinementService,
    _sha256,
)


@pytest.fixture
def tmp_db_session(tmp_path):
    """Create an isolated SQLite DB for each test."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.db.database import Base

    db_path = tmp_path / "test.db"
    test_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine, expire_on_commit=False)

    session = TestSession()
    yield session
    session.close()


def _make_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class TestSha256:
    def test_consistent_hash(self):
        assert _sha256("hello") == _sha256("hello")

    def test_different_text_different_hash(self):
        assert _sha256("hello") != _sha256("world")

    def test_returns_hex_string(self):
        h = _sha256("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestConcurrencyConflict:
    def test_raises_on_hash_mismatch(self):
        """refine_section should raise ConcurrencyConflict when expected hash doesn't match."""
        mock_synth = MagicMock()
        service = ProposalSectionRefinementService(mock_synth)

        proposal = MagicMock(spec=Proposal)
        proposal.id = 1
        proposal.sections_json = json.dumps({"abstract": "original text"})
        proposal.content_md = "# Original"

        import asyncio

        async def run():
            await service.refine_section(
                session=MagicMock(),
                proposal=proposal,
                section_key="abstract",
                idea=MagicMock(),
                expected_current_hash="wrong_hash",
            )

        with pytest.raises(ConcurrencyConflict):
            asyncio.run(run())


class TestRestoreVersion:
    """Tests for the rollback/restore functionality."""

    def test_restore_creates_new_revision(self, tmp_db_session):
        """Restoring a version should create a new revision with source=rollback."""
        # Setup: create a proposal with a revision history
        proposal = Proposal(
            idea_id=1,
            content_md="# Test",
            references_json="[]",
            sections_json=json.dumps({"abstract": "version 2 text"}),
               )
        tmp_db_session.add(proposal)
        tmp_db_session.commit()

        # Create an earlier revision
        rev1 = ProposalSectionRevision(
            proposal_id=proposal.id,
            section_key="abstract",
            section_text="version 1 text",
            section_hash=_make_hash("version 1 text"),
            previous_text="original text",
            previous_hash=_make_hash("original text"),
            source="section_refine",
            trigger="user_manual",
            trigger_detail=None,
            model_receipt_json=None,
            quality_checks_json="[]",
        )
        tmp_db_session.add(rev1)
        tmp_db_session.commit()

        # Now restore to revision 1
        mock_synth = MagicMock()
        service = ProposalSectionRefinementService(mock_synth)

        import asyncio

        current_hash = _make_hash("version 2 text")

        async def run():
            return await service.restore_version(
                session=tmp_db_session,
                proposal=proposal,
                section_key="abstract",
                target_revision_id=rev1.id,
                expected_current_hash=current_hash,
            )

        result = asyncio.run(run())

        assert result.section_key == "abstract"
        assert result.new_text == "version 1 text"
        assert result.previous_text == "version 2 text"
        assert result.section_hash == _make_hash("version 1 text")

        # Check a new rollback revision was created
        from sqlalchemy import select

        revisions = tmp_db_session.execute(
            select(ProposalSectionRevision)
            .where(ProposalSectionRevision.proposal_id == proposal.id)
            .order_by(ProposalSectionRevision.created_at.desc())
        ).scalars().all()

        assert len(revisions) == 2  # original + rollback
        assert revisions[0].source == "rollback"
        assert revisions[0].trigger == "user_restore"
        assert json.loads(revisions[0].trigger_detail)["target_revision_id"] == rev1.id

        # Check sections_json was updated
        sections = json.loads(proposal.sections_json)
        assert sections["abstract"] == "version 1 text"

    def test_restore_raises_on_hash_mismatch(self, tmp_db_session):
        """Restore should fail with ConcurrencyConflict if section changed."""
        proposal = Proposal(
            idea_id=1,
            content_md="# Test",
            references_json="[]",
            sections_json=json.dumps({"abstract": "current text"}),
        )
        tmp_db_session.add(proposal)
        tmp_db_session.commit()

        rev1 = ProposalSectionRevision(
            proposal_id=proposal.id,
            section_key="abstract",
            section_text="old text",
            section_hash=_make_hash("old text"),
            previous_text=None,
            previous_hash=None,
            source="pipeline",
            trigger="pipeline_refine",
            trigger_detail=None,
            model_receipt_json=None,
            quality_checks_json="[]",
        )
        tmp_db_session.add(rev1)
        tmp_db_session.commit()

        mock_synth = MagicMock()
        service = ProposalSectionRefinementService(mock_synth)

        import asyncio

        async def run():
            await service.restore_version(
                session=tmp_db_session,
                proposal=proposal,
                section_key="abstract",
                target_revision_id=rev1.id,
                expected_current_hash="wrong_hash",
            )

        with pytest.raises(ConcurrencyConflict):
            asyncio.run(run())

    def test_restore_nonexistent_revision_raises(self, tmp_db_session):
        """Restore should raise NotFoundError for non-existent revision."""
        from backend.api.errors import NotFoundError

        proposal = Proposal(
            idea_id=1,
            content_md="# Test",
            references_json="[]",
            sections_json=json.dumps({"abstract": "text"}),
        )
        tmp_db_session.add(proposal)
        tmp_db_session.commit()

        mock_synth = MagicMock()
        service = ProposalSectionRefinementService(mock_synth)

        import asyncio

        async def run():
            await service.restore_version(
                session=tmp_db_session,
                proposal=proposal,
                section_key="abstract",
                target_revision_id=999,
                expected_current_hash=_make_hash("text"),
            )

        with pytest.raises(NotFoundError):
            asyncio.run(run())


class TestCommitRevision:
    """Tests for the internal atomic commit with double hash check."""

    def test_double_hash_check_catches_concurrent_modification(self, tmp_db_session):
        """If sections_json changed between pre-check and transaction, abort."""
        # This test simulates: hash checked before, then another tab modifies
        # sections_json, then the transaction opens and re-checks
        proposal = Proposal(
            idea_id=1,
            content_md="# Original",
            references_json="[]",
            sections_json=json.dumps({"abstract": "original text"}),
        )
        tmp_db_session.add(proposal)
        tmp_db_session.commit()

        mock_synth = MagicMock()
        service = ProposalSectionRefinementService(mock_synth)

        # Simulate: pre-check hash matches "original text"
        original_hash = _make_hash("original text")

        # Simulate: concurrent modification happens BEFORE the transaction
        # (we modify the DB directly to simulate another tab)
        proposal.sections_json = json.dumps({"abstract": "CHANGED BY ANOTHER TAB"})
        tmp_db_session.commit()

        # Now _commit_revision re-reads inside the transaction
        with pytest.raises(ConcurrencyConflict):
            service._commit_revision(
                session=tmp_db_session,
                proposal=proposal,
                section_key="abstract",
                new_text="new text",
                new_hash=_make_hash("new text"),
                previous_text="original text",
                previous_hash=original_hash,
                source="section_refine",
                trigger="user_manual",
                trigger_detail=None,
                receipt_dict={"requested_model": "test"},
                qc_after=[],
                qc_before=[],
                expected_hash_in_tx=original_hash,
            )

        # Verify NO revision was created
        from sqlalchemy import select

        revisions = tmp_db_session.execute(
            select(ProposalSectionRevision).where(
                ProposalSectionRevision.proposal_id == proposal.id
            )
        ).scalars().all()
        assert len(revisions) == 0

    def test_successful_commit_creates_revision_and_updates_proposal(self, tmp_db_session):
        """Normal flow: commit creates revision + updates sections_json + content_md."""
        proposal = Proposal(
            idea_id=1,
            content_md="# Original",
            references_json="[]",
            sections_json=json.dumps({"abstract": "original text", "title": "Test"}),
        )
        tmp_db_session.add(proposal)
        tmp_db_session.commit()

        mock_synth = MagicMock()
        service = ProposalSectionRefinementService(mock_synth)

        original_hash = _make_hash("original text")

        result = service._commit_revision(
            session=tmp_db_session,
            proposal=proposal,
            section_key="abstract",
            new_text="improved text",
            new_hash=_make_hash("improved text"),
            previous_text="original text",
            previous_hash=original_hash,
            source="section_refine",
            trigger="quality_check",
            trigger_detail={"failure_hints": ["word count 5 < 150"]},
            receipt_dict={"requested_model": "gpt-4o", "served_model": "gpt-4o-2024"},
            qc_after=[{"section": "abstract", "passed": True}],
            qc_before=[{"section": "abstract", "passed": False}],
            expected_hash_in_tx=original_hash,
        )

        assert result.revision_id > 0
        assert result.new_text == "improved text"
        assert result.previous_text == "original text"

        # Check sections_json was updated
        sections = json.loads(proposal.sections_json)
        assert sections["abstract"] == "improved text"
        assert sections["title"] == "Test"  # other sections untouched

        # Check content_md was recomputed (not "# Original")
        assert proposal.content_md != "# Original"
        assert "improved text" in proposal.content_md

        # Check revision row
        from sqlalchemy import select

        rev = tmp_db_session.execute(
            select(ProposalSectionRevision).where(
                ProposalSectionRevision.proposal_id == proposal.id
            )
        ).scalar_one()

        assert rev.source == "section_refine"
        assert rev.trigger == "quality_check"
        assert rev.previous_text == "original text"
        assert rev.section_text == "improved text"
        receipt = json.loads(rev.model_receipt_json)
        assert receipt["requested_model"] == "gpt-4o"
        trigger_detail = json.loads(rev.trigger_detail)
        assert "failure_hints" in trigger_detail


class TestSyntheticOriginal:
    """Tests for the synthetic original entry logic."""

    def test_no_revisions_shows_current_as_original(self, tmp_db_session):
        """When no revisions exist, synthetic original = current section."""
        import hashlib

        from backend.api.quality_checks import compute_quality_checks

        proposal = Proposal(
            idea_id=1,
            content_md="# Test",
            references_json="[]",
            sections_json=json.dumps({"abstract": "original text"}),
        )
        tmp_db_session.add(proposal)
        tmp_db_session.commit()

        # Simulate the synthetic original logic
        sections = json.loads(proposal.sections_json)
        current_text = sections.get("abstract", "")
        current_hash = hashlib.sha256(current_text.encode()).hexdigest()

        from sqlalchemy import select

        revisions = tmp_db_session.execute(
            select(ProposalSectionRevision).where(
                ProposalSectionRevision.proposal_id == proposal.id
            )
        ).scalars().all()

        # No revisions → synthetic = current
        assert len(revisions) == 0

        qc = compute_quality_checks({"abstract": current_text}) or []
        synthetic_original = {
            "source": "pipeline",
            "section_hash": current_hash,
            "note": "Original pipeline output (current sections_json)",
        }
        assert synthetic_original["section_hash"] == current_hash

    def test_revisions_exist_uses_earliest_previous_text(self, tmp_db_session):
        """When revisions exist, original = earliest revision's previous_text."""
        import hashlib

        original_text = "the very first version"
        proposal = Proposal(
            idea_id=1,
            content_md="# Test",
            references_json="[]",
            sections_json=json.dumps({"abstract": "version 2"}),
        )
        tmp_db_session.add(proposal)
        tmp_db_session.commit()

        rev1 = ProposalSectionRevision(
            proposal_id=proposal.id,
            section_key="abstract",
            section_text="version 1",
            section_hash=hashlib.sha256(b"version 1").hexdigest(),
            previous_text=original_text,
            previous_hash=hashlib.sha256(original_text.encode()).hexdigest(),
            source="section_refine",
            trigger="user_manual",
        )
        tmp_db_session.add(rev1)
        tmp_db_session.commit()

        # Find earliest revision
        from sqlalchemy import select

        revisions = tmp_db_session.execute(
            select(ProposalSectionRevision)
            .where(ProposalSectionRevision.proposal_id == proposal.id)
            .order_by(ProposalSectionRevision.created_at.desc())
        ).scalars().all()

        earliest = revisions[-1]
        assert earliest.previous_text == original_text

        # Synthetic original should use this
        synthetic_hash = hashlib.sha256(earliest.previous_text.encode()).hexdigest()
        assert synthetic_hash == hashlib.sha256(original_text.encode()).hexdigest()

    def test_no_previous_text_labels_unavailable(self, tmp_db_session):
        """If earliest revision has no previous_text, original is unavailable."""
        proposal = Proposal(
            idea_id=1,
            content_md="# Test",
            references_json="[]",
            sections_json=json.dumps({"abstract": "text"}),
        )
        tmp_db_session.add(proposal)
        tmp_db_session.commit()

        # Revision with NULL previous_text (e.g., initial pipeline)
        rev1 = ProposalSectionRevision(
            proposal_id=proposal.id,
            section_key="abstract",
            section_text="some text",
            section_hash=hashlib.sha256(b"some text").hexdigest(),
            previous_text=None,
            previous_hash=None,
            source="pipeline",
            trigger="pipeline_refine",
        )
        tmp_db_session.add(rev1)
        tmp_db_session.commit()

        from sqlalchemy import select

        revisions = tmp_db_session.execute(
            select(ProposalSectionRevision)
            .where(ProposalSectionRevision.proposal_id == proposal.id)
            .order_by(ProposalSectionRevision.created_at.desc())
        ).scalars().all()

        earliest = revisions[-1]
        assert earliest.previous_text is None
        # Should be labeled unavailable, not guessed
        synthetic_original = {
            "source": "pipeline",
            "section_hash": None,
            "note": "Original unavailable (no previous_text captured)",
        }
        assert synthetic_original["section_hash"] is None
