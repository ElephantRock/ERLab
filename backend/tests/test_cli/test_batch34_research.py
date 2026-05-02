"""Tests for BATCH-34 TASK-03: CLI research commands (open, proposal, export)."""

import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.database import Base
from backend.db.models import Idea, Proposal


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_idea(db_session):
    idea = Idea(
        id=1,
        title="Test Research Idea",
        problem_statement="Testing CLI export",
        proposed_method="Unit tests",
        expected_contributions="Quality assurance",
        domain="AI/NLP",
        novelty_score=0.85,
        feasibility_score=7.2,
        overall_score=0.78,
    )
    db_session.add(idea)
    db_session.commit()
    db_session.refresh(idea)
    return idea


@pytest.fixture
def sample_idea_with_proposal(db_session, sample_idea):
    proposal = Proposal(
        idea_id=sample_idea.id,
        content_md="# Proposal\n\nThis is the proposal content.",
    )
    db_session.add(proposal)
    db_session.commit()
    return sample_idea


@contextmanager
def _session_ctx(session):
    """Mimic get_session() context manager."""
    yield session


# ── TEST-34-03-01: erock open {id} opens idea in browser ─────────


def test_34_03_01_open_idea_opens_browser(db_session, sample_idea):
    """Verify that erock open {id} opens the correct URL in the browser."""
    from typer.testing import CliRunner
    from backend.cli.main import app

    runner = CliRunner()

    with patch("backend.db.database.get_session", return_value=_session_ctx(db_session)), \
         patch("backend.db.crud.get_idea", return_value=sample_idea), \
         patch("backend.cli.commands.research.webbrowser.open") as mock_open:

        result = runner.invoke(app, ["research", "open", "1"])

    assert result.exit_code == 0
    mock_open.assert_called_once()
    opened_url = mock_open.call_args[0][0]
    assert "/ideas/1" in opened_url


# ── TEST-34-03-02: erock proposal {id} generates proposal ────────


def test_34_03_02_proposal_generates_for_idea(db_session, sample_idea):
    """Verify that erock proposal {id} invokes the proposal synthesizer."""
    from typer.testing import CliRunner
    from backend.cli.main import app

    runner = CliRunner()

    mock_proposal = MagicMock()
    mock_proposal.title = "Generated Proposal"
    mock_proposal.content_md = "## Introduction\n\nTest proposal content."
    mock_proposal.content_latex = None

    with patch("backend.db.database.get_session", return_value=_session_ctx(db_session)), \
         patch("backend.db.crud.get_idea", return_value=sample_idea), \
         patch("backend.cli.commands.research._run_async", return_value=mock_proposal):

        result = runner.invoke(app, ["research", "proposal", "1"])

    assert result.exit_code == 0
    assert "Proposal generated" in result.output or "Generating proposal" in result.output


# ── TEST-34-03-03: erock export {id} exports to file ─────────────


def test_34_03_03_export_idea_to_markdown(db_session, sample_idea_with_proposal, tmp_path):
    """Verify that erock export {id} writes idea data to a markdown file."""
    from typer.testing import CliRunner
    from backend.cli.main import app

    runner = CliRunner()
    output_file = tmp_path / "idea_export.md"

    with patch("backend.db.database.get_session", return_value=_session_ctx(db_session)), \
         patch("backend.db.crud.get_idea", return_value=sample_idea_with_proposal), \
         patch("backend.db.crud.get_proposal_by_idea", return_value=MagicMock(
             content_md="# Proposal\n\nThis is the proposal content."
         )):

        result = runner.invoke(app, [
            "research", "export", "1",
            "--output", str(output_file),
            "--format", "markdown",
        ])

    assert result.exit_code == 0
    assert output_file.exists()

    content = output_file.read_text(encoding="utf-8")
    assert "Test Research Idea" in content
    assert "Testing CLI export" in content
    assert "Unit tests" in content
    assert "0.85" in content  # novelty score


def test_34_03_03b_export_idea_to_json(db_session, sample_idea, tmp_path):
    """Verify that erock export {id} --format json writes valid JSON."""
    from typer.testing import CliRunner
    from backend.cli.main import app

    runner = CliRunner()
    output_file = tmp_path / "idea_export.json"

    with patch("backend.db.database.get_session", return_value=_session_ctx(db_session)), \
         patch("backend.db.crud.get_idea", return_value=sample_idea), \
         patch("backend.db.crud.get_proposal_by_idea", return_value=None):

        result = runner.invoke(app, [
            "research", "export", "1",
            "--output", str(output_file),
            "--format", "json",
        ])

    assert result.exit_code == 0
    assert output_file.exists()

    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert data["title"] == "Test Research Idea"
    assert data["domain"] == "AI/NLP"
    assert data["novelty_score"] == 0.85
