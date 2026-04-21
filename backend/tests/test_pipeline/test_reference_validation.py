"""Tests for ReferenceValidator from backend.pipeline.synthesis.reference_validator (P14)."""

import sys
from unittest.mock import MagicMock

sys.modules.setdefault("chromadb", MagicMock())

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.database import Base
from backend.db.models import Paper
from backend.pipeline.synthesis.reference_validator import ReferenceValidator


def _make_db_session_with_paper(doi: str, title: str = "Test Paper"):
    """Create an in-memory SQLite session with one paper having the given DOI."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    paper = Paper(
        source_id="test-1",
        source="test",
        title=title,
        doi=doi,
    )
    session.add(paper)
    session.commit()
    return session


def test_validate_with_doi_match():
    """Session has a paper with matching DOI, returns verified_doi."""
    session = _make_db_session_with_paper("10.1234/test-doi")
    validator = ReferenceValidator(session=session, store=None)

    refs = [
        {"title": "Some Paper", "doi": "10.1234/test-doi"},
        {"title": "Another Paper", "doi": "10.9999/no-match"},
    ]

    results = asyncio_run(validator.validate(refs))

    assert len(results) == 2
    assert results[0].status == "verified_doi"
    assert results[0].title == "Some Paper"
    assert results[1].status == "unverified"


def test_validate_unverified():
    """No session, no store -- all references are unverified."""
    validator = ReferenceValidator(session=None, store=None)

    refs = [
        {"title": "Paper A", "doi": "10.1234/a"},
        {"title": "Paper B", "doi": "10.1234/b"},
    ]

    results = asyncio_run(validator.validate(refs))

    assert len(results) == 2
    assert all(r.status == "unverified" for r in results)


def test_validate_mixed_references():
    """Mix of structured dicts and non-dict refs."""
    session = _make_db_session_with_paper("10.1234/match")
    validator = ReferenceValidator(session=session, store=None)

    refs = [
        {"title": "Matched Paper", "doi": "10.1234/match"},
        "Plain string reference",
        {"title": "No DOI Paper"},
    ]

    results = asyncio_run(validator.validate(refs))

    assert len(results) == 3
    assert results[0].status == "verified_doi"
    assert results[0].reference_index == 0
    assert results[1].status == "unverified"
    assert results[1].title == "Plain string reference"
    assert results[2].status == "unverified"
    assert results[2].title == "No DOI Paper"


def asyncio_run(coro):
    """Helper: run an async coroutine synchronously."""
    import asyncio

    return asyncio.run(coro)
