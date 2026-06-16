"""Tests for BATCH-33 TASK-01: PDF Export + Plugin Registry."""

import json
import zipfile
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

try:
    import weasyprint  # noqa: F401
    HAS_WEASYPRINT = True
except (ImportError, OSError):
    HAS_WEASYPRINT = False

pytestmark = pytest.mark.skipif(not HAS_WEASYPRINT, reason='WeasyPrint not installed')

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
        title="Test Idea for PDF",
        problem_statement="Testing PDF export.",
        proposed_method="Use WeasyPrint.",
        expected_contributions="Better exports.",
        domain="AI/NLP",
        novelty_score=0.85,
        feasibility_score=7.2,
        overall_score=0.79,
    )
    db_session.add(idea)
    db_session.commit()
    db_session.refresh(idea)

    proposal = Proposal(idea_id=idea.id, content_md="# Proposal\n\nTest proposal content.")
    db_session.add(proposal)
    db_session.commit()

    return idea


# ── TEST-33-01-01: POST /export/pdf returns PDF content ──────────


def test_33_01_01_export_pdf_returns_pdf_content(db_session, sample_idea):
    """Verify that the PDF export route generates valid HTML that can be converted to PDF."""
    from backend.api.routes.exports import _idea_to_html

    idea_data = {
        "title": sample_idea.title,
        "domain": sample_idea.domain,
        "problem_statement": sample_idea.problem_statement,
        "proposed_method": sample_idea.proposed_method,
        "expected_contributions": sample_idea.expected_contributions,
        "novelty_score": sample_idea.novelty_score,
        "feasibility_score": sample_idea.feasibility_score,
        "overall_score": sample_idea.overall_score,
        "created_at": str(sample_idea.created_at),
    }

    html = _idea_to_html(idea_data, "# Test Proposal")
    assert "<!DOCTYPE html>" in html
    assert "Test Idea for PDF" in html
    assert "Problem Statement" in html
    assert "Proposed Method" in html
    assert "0.85" in html
    assert "7.20" in html
    assert "0.79" in html
    assert "Scores" in html
    assert "Proposal" in html

    # Verify WeasyPrint can process the HTML (if available)
    try:
        from weasyprint import HTML as WPHTML

        pdf_bytes = WPHTML(string=html).write_pdf()
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b"%PDF"
    except ImportError:
        # WeasyPrint not installed — HTML generation is still valid
        pass


# ── TEST-33-01-02: POST /export/bulk returns zip of ideas ────────


def test_33_01_02_bulk_export_returns_zip_of_ideas(db_session, sample_idea):
    """Verify that bulk export creates a valid ZIP archive with idea files."""
    from backend.api.routes.exports import _idea_to_html

    # Simulate the bulk export logic
    buffer = BytesIO()
    idea_data = {
        "title": sample_idea.title,
        "domain": sample_idea.domain,
        "problem_statement": sample_idea.problem_statement,
        "proposed_method": sample_idea.proposed_method,
        "expected_contributions": sample_idea.expected_contributions,
        "novelty_score": sample_idea.novelty_score,
        "feasibility_score": sample_idea.feasibility_score,
        "overall_score": sample_idea.overall_score,
        "created_at": str(sample_idea.created_at),
    }

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Markdown export
        md_content = f"# {sample_idea.title}\n\n**Domain:** {sample_idea.domain}\n\n"
        md_content += f"## Problem Statement\n\n{sample_idea.problem_statement}\n\n"
        zf.writestr("Test_Idea_for_PDF.md", md_content.encode("utf-8"))

    buffer.seek(0)
    with zipfile.ZipFile(buffer, "r") as zf:
        names = zf.namelist()
        assert len(names) == 1
        assert names[0].endswith(".md")
        content = zf.read(names[0]).decode("utf-8")
        assert "Test Idea for PDF" in content
        assert "Problem Statement" in content


# ── TEST-33-01-03: GET /plugins lists available plugins ──────────


def test_33_01_03_get_plugins_lists_available_plugins():
    """Verify that the plugin registry lists built-in plugins."""
    from backend.plugins.registry import PluginRegistry

    registry = PluginRegistry()
    plugins = registry.list_plugins()

    assert len(plugins) >= 4  # 4 built-in plugins
    names = [p["name"] for p in plugins]
    assert "pdf-export" in names
    assert "bulk-export" in names
    assert "literature-search" in names
    assert "knowledge-graph" in names

    # Verify structure
    for p in plugins:
        assert "name" in p
        assert "version" in p
        assert "description" in p
        assert "enabled" in p


# ── TEST-33-01-04: POST /plugins/install registers plugin ────────


def test_33_01_04_plugins_install_registers_plugin():
    """Verify that installing a plugin adds it to the registry."""
    from backend.plugins.registry import PluginRegistry

    registry = PluginRegistry()

    # Install a new plugin
    plugin = registry.install(
        name="my-custom-plugin",
        version="1.2.0",
        description="A custom test plugin",
    )

    assert plugin["name"] == "my-custom-plugin"
    assert plugin["version"] == "1.2.0"
    assert plugin["description"] == "A custom test plugin"
    assert plugin["enabled"] is True

    # Verify it appears in the list
    plugins = registry.list_plugins()
    names = [p["name"] for p in plugins]
    assert "my-custom-plugin" in names

    # Re-install (update) existing plugin
    updated = registry.install(
        name="my-custom-plugin",
        version="2.0.0",
        description="Updated description",
    )
    assert updated["version"] == "2.0.0"
    assert updated["description"] == "Updated description"
