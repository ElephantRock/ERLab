"""Tests for BATCH-84 — Research Journal per Pipeline Run.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import os
import tempfile
import pytest

from backend.pipeline.journal.writer import JournalWriter


@pytest.fixture
def tmp_journal():
    with tempfile.TemporaryDirectory() as tmpdir:
        journal = JournalWriter(run_id="run_test", domain="AI/NLP", output_dir=tmpdir)
        yield journal


def test_84_01_01_add_note():
    """add_note stores entry."""
    journal = JournalWriter(run_id="test")
    journal.add_note("ingestion", "Found 23 papers from arXiv")
    assert len(journal.entries) == 1
    assert journal.entries[0]["stage"] == "ingestion"
    assert "23 papers" in journal.entries[0]["message"]


def test_84_01_02_write_generates_files(tmp_journal):
    """write() generates notes.md and README.md."""
    tmp_journal.add_note("literature_search", "Searching arXiv...")
    tmp_journal.add_note("gap_analysis", "Found 5 gaps")
    notes_path, readme_path = tmp_journal.write()
    assert notes_path.exists()
    assert readme_path.exists()


def test_84_01_03_notes_md_contains_entries(tmp_journal):
    """notes.md contains all stage entries."""
    tmp_journal.add_note("ingestion", "Ingested 30 papers")
    tmp_journal.add_note("gap_analysis", "Identified 3 gaps")
    _, _ = tmp_journal.write()
    notes = (tmp_journal.output_dir / "notes.md").read_text()
    assert "Ingested 30 papers" in notes
    assert "Identified 3 gaps" in notes


def test_84_01_04_readme_md_contains_summary(tmp_journal):
    """README.md contains run summary table."""
    tmp_journal.add_note("synthesis", "Generated 2 proposals")
    _, _ = tmp_journal.write()
    readme = (tmp_journal.output_dir / "README.md").read_text()
    assert "AI/NLP" in readme
    assert "run_test" in readme
    assert "Synthesis" in readme


def test_84_01_05_no_sensitive_data(tmp_journal):
    """Journal scrubs API keys from messages (HB-01)."""
    tmp_journal.add_note("test", "Using API key sk-12345 for search")
    notes = tmp_journal._generate_notes()
    assert "sk-12345" not in notes
    assert "REDACTED" in notes


def test_84_01_06_empty_journal_still_writes(tmp_journal):
    """Empty journal still produces valid files."""
    notes_path, readme_path = tmp_journal.write()
    assert notes_path.exists()
    assert readme_path.exists()
    readme = readme_path.read_text()
    assert "run_test" in readme


# TASK-02 tests

def test_84_02_01_journal_has_domain_and_run_id():
    """Journal captures domain and run_id."""
    j = JournalWriter(run_id="run_20260506", domain="Biology")
    assert j.run_id == "run_20260506"
    assert j.domain == "Biology"


def test_84_02_02_multiple_stages_grouped(tmp_journal):
    """Notes are grouped by stage in notes.md."""
    tmp_journal.add_note("ingestion", "Step 1")
    tmp_journal.add_note("gap_analysis", "Step 2")
    tmp_journal.add_note("gap_analysis", "Step 3")
    notes = tmp_journal._generate_notes()
    assert "## Ingestion" in notes
    assert "## Gap Analysis" in notes
