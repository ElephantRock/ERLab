"""Tests for BATCH-106 — Proposal Versioning.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import os
import tempfile
import pytest

from backend.pipeline.versioning import ProposalVersionStore, ProposalVersion


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = ProposalVersionStore(db_path=os.path.join(tmpdir, "versions.db"))
        yield s
        s.close()


def test_106_01_save_and_get(store):
    """Save a version and retrieve it."""
    v = store.save(ProposalVersion(proposal_id="prop-1", version=0, content="Version 1 content"))
    assert v == 1
    result = store.get("prop-1", 1)
    assert result is not None
    assert result.content == "Version 1 content"


def test_106_01_auto_increment(store):
    """Versions auto-increment."""
    store.save(ProposalVersion(proposal_id="p1", version=0, content="V1"))
    v2 = store.save(ProposalVersion(proposal_id="p1", version=0, content="V2"))
    assert v2 == 2


def test_106_01_get_latest(store):
    """get with no version returns latest."""
    store.save(ProposalVersion(proposal_id="p1", version=0, content="V1"))
    store.save(ProposalVersion(proposal_id="p1", version=0, content="V2"))
    latest = store.get("p1")
    assert latest.version == 2
    assert latest.content == "V2"


def test_106_02_list_versions(store):
    """list_versions returns all version numbers."""
    store.save(ProposalVersion(proposal_id="p1", version=0, content="V1"))
    store.save(ProposalVersion(proposal_id="p1", version=0, content="V2"))
    store.save(ProposalVersion(proposal_id="p1", version=0, content="V3"))
    versions = store.list_versions("p1")
    assert versions == [1, 2, 3]


def test_106_02_diff(store):
    """diff generates unified diff between versions."""
    store.save(ProposalVersion(proposal_id="p1", version=0, content="Line A\nLine B\nLine C"))
    store.save(ProposalVersion(proposal_id="p1", version=0, content="Line A\nLine D\nLine C"))
    diff_text = store.diff("p1", 1, 2)
    assert "Line D" in diff_text
    assert "Line B" in diff_text
    assert "-Line B" in diff_text or "+Line D" in diff_text


def test_106_02_diff_nonexistent(store):
    """diff with nonexistent versions returns error message."""
    diff_text = store.diff("nonexistent", 1, 2)
    assert "not found" in diff_text


def test_106_03_count(store):
    """count returns correct totals."""
    store.save(ProposalVersion(proposal_id="p1", version=0, content="V1"))
    store.save(ProposalVersion(proposal_id="p1", version=0, content="V2"))
    store.save(ProposalVersion(proposal_id="p2", version=0, content="V1"))
    assert store.count() == 3
    assert store.count(proposal_id="p1") == 2


def test_106_03_get_nonexistent(store):
    """get returns None for nonexistent proposal."""
    assert store.get("nonexistent") is None
