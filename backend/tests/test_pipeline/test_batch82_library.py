"""Tests for BATCH-82 — Knowledge Library (Persistent Research Memory).

TASK-01: KnowledgeLibrary Core (8 tests)
TASK-02: Library Indexer (4 tests)

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import json
import os
import tempfile
import pytest
from unittest.mock import MagicMock

from backend.pipeline.knowledge.library import KnowledgeLibrary, LibraryEntry
from backend.pipeline.knowledge.library_indexer import LibraryIndexer


@pytest.fixture
def tmp_library():
    """Create a temporary knowledge library."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_library.db")
        lib = KnowledgeLibrary(db_path=db_path)
        yield lib
        lib.close()


@pytest.fixture
def mock_paper():
    p = MagicMock()
    p.title = "Sparse Transformers for Efficient Sequence Modeling"
    p.doi = "10.1234/test.2024"
    p.year = 2024
    p.abstract = "We propose sparse attention..."
    p.authors = ["Author A", "Author B"]
    return p


@pytest.fixture
def mock_gap():
    g = MagicMock()
    g.title = "No efficient sparse attention for edge devices"
    g.description = "Existing methods require too much memory."
    return g


@pytest.fixture
def mock_idea():
    i = MagicMock()
    i.title = "Adaptive Sparse Mask Learning"
    i.description = "Learn sparse masks from data distribution."
    i.novelty_score = 0.85
    return i


# ══════════════════════════════════════════════════════════
# TASK-01: KnowledgeLibrary Core
# ══════════════════════════════════════════════════════════

def test_82_01_01_add_entry_returns_true(tmp_library, mock_paper):
    """Adding a new entry returns True."""
    entry = LibraryEntry(entry_type="paper", domain="AI/NLP", title=mock_paper.title, content="{}")
    assert tmp_library.add(entry) is True


def test_82_01_02_duplicate_returns_false(tmp_library, mock_paper):
    """Adding the same title twice returns False (HB-02)."""
    entry = LibraryEntry(entry_type="paper", domain="AI/NLP", title=mock_paper.title, content="{}")
    assert tmp_library.add(entry) is True
    assert tmp_library.add(entry) is False


def test_82_01_03_query_by_domain(tmp_library, mock_paper):
    """Query by domain returns matching entries."""
    entry = LibraryEntry(entry_type="paper", domain="AI/NLP", title=mock_paper.title, content="{}")
    tmp_library.add(entry)
    results = tmp_library.query("AI/NLP")
    assert len(results) == 1
    assert results[0]["title"] == mock_paper.title


def test_82_01_04_query_by_type(tmp_library, mock_paper, mock_gap):
    """Query with entry_type filter works."""
    tmp_library.add(LibraryEntry(entry_type="paper", domain="AI/NLP", title=mock_paper.title, content="{}"))
    tmp_library.add(LibraryEntry(entry_type="gap", domain="AI/NLP", title=mock_gap.title, content="{}"))
    papers = tmp_library.query("AI/NLP", entry_type="paper")
    gaps = tmp_library.query("AI/NLP", entry_type="gap")
    assert len(papers) == 1
    assert len(gaps) == 1


def test_82_01_05_count(tmp_library, mock_paper, mock_gap):
    """Count entries correctly."""
    tmp_library.add_papers([mock_paper], "AI/NLP")
    tmp_library.add_gaps([mock_gap], "AI/NLP")
    assert tmp_library.count() == 2
    assert tmp_library.count(domain="AI/NLP") == 2
    assert tmp_library.count(entry_type="paper") == 1


def test_82_01_06_add_papers_bulk(tmp_library):
    """Bulk add papers with dedup."""
    papers = []
    for i in range(5):
        p = MagicMock()
        p.title = f"Paper {i}"
        p.doi = f"10.1234/paper{i}"
        p.year = 2024
        p.abstract = f"Abstract {i}"
        p.authors = []
        papers.append(p)
    # Add duplicate
    dup = MagicMock()
    dup.title = "Paper 0"
    dup.doi = "10.1234/paper0"
    dup.year = 2024
    dup.abstract = "Duplicate"
    dup.authors = []

    added = tmp_library.add_papers(papers, "AI/NLP")
    assert added == 5
    added_dup = tmp_library.add_papers([dup], "AI/NLP")
    assert added_dup == 0  # Dedup


def test_82_01_07_dedup_key_deterministic():
    """Same title produces same dedup_key."""
    e1 = LibraryEntry(entry_type="paper", domain="test", title="Same Title", content="{}")
    e2 = LibraryEntry(entry_type="paper", domain="test", title="same title", content="{}")  # case
    e3 = LibraryEntry(entry_type="paper", domain="test", title="Same Title ", content="{}")  # trailing space
    assert e1.compute_dedup_key() == e2.compute_dedup_key()
    assert e1.compute_dedup_key() == e3.compute_dedup_key()


def test_82_01_08_empty_query_returns_empty(tmp_library):
    """Query on empty library returns empty list."""
    results = tmp_library.query("nonexistent")
    assert results == []


# ══════════════════════════════════════════════════════════
# TASK-02: Library Indexer
# ══════════════════════════════════════════════════════════

def test_82_02_01_index_run_counts_correctly(tmp_library, mock_paper, mock_gap, mock_idea):
    """index_run returns correct counts."""
    indexer = LibraryIndexer(library=tmp_library)
    counts = indexer.index_run(
        domain="AI/NLP",
        run_id="run_test",
        papers=[mock_paper],
        gaps=[mock_gap],
        ideas=[mock_idea],
    )
    assert counts["papers"] == 1
    assert counts["gaps"] == 1
    assert counts["ideas"] == 1
    assert counts["total"] == 3


def test_82_02_02_get_existing_papers(tmp_library, mock_paper):
    """get_existing_papers returns indexed papers."""
    tmp_library.add_papers([mock_paper], "AI/NLP")
    indexer = LibraryIndexer(library=tmp_library)
    papers = indexer.get_existing_papers("AI/NLP")
    assert len(papers) == 1
    assert papers[0]["title"] == mock_paper.title


def test_82_02_03_index_run_handles_none_gracefully(tmp_library):
    """index_run with None lists doesn't crash."""
    indexer = LibraryIndexer(library=tmp_library)
    counts = indexer.index_run(domain="AI/NLP", run_id="test", papers=None, gaps=None, ideas=None)
    assert counts["total"] == 0


def test_82_02_04_query_failure_returns_empty(tmp_library):
    """Query failure returns empty list (HB-03)."""
    indexer = LibraryIndexer(library=tmp_library)
    # Close the connection to simulate failure
    tmp_library.close()
    # This should return empty, not crash
    results = indexer.get_existing_papers("AI/NLP")
    assert isinstance(results, list)
