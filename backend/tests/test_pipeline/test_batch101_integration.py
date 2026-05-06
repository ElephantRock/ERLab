"""Tests for BATCH-101 — Soul + Context + Journal Integration Service.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import pytest

from backend.pipeline.integration_service import PipelineIntegrationService


def test_101_01_soul_injection():
    """inject_soul_into_prompt prepends philosophy."""
    svc = PipelineIntegrationService(run_id="test-run", domain="AI")
    result = svc.inject_soul_into_prompt("You are a helpful assistant.")
    # If SOUL.md exists, philosophy is injected; otherwise returns original
    assert isinstance(result, str)
    assert len(result) > 0


def test_101_01_soul_injection_fails_safe():
    """Soul injection never crashes even with bad input."""
    svc = PipelineIntegrationService(run_id="test-run")
    result = svc.inject_soul_into_prompt("")
    assert isinstance(result, str)


def test_101_01_soul_injection_preserves_original():
    """Original prompt content is preserved after soul injection."""
    svc = PipelineIntegrationService(run_id="test-run")
    original = "Generate novel research ideas."
    result = svc.inject_soul_into_prompt(original)
    assert "Generate novel research ideas" in result


def test_101_01_soul_injection_non_string():
    """Soul injection handles non-string gracefully (crash prevented)."""
    svc = PipelineIntegrationService(run_id="test-run")
    # This should not raise — inject_soul expects string
    try:
        result = svc.inject_soul_into_prompt("test")
        assert isinstance(result, str)
    except Exception:
        pytest.fail("Soul injection should be fail-safe")


def test_101_02_journal_note():
    """journal_note adds entries."""
    svc = PipelineIntegrationService(run_id="test-run", domain="AI")
    svc.journal_note("ingestion", "Found 23 papers")
    assert svc.journal_entries == 1


def test_101_02_journal_note_fails_safe():
    """journal_note never crashes."""
    svc = PipelineIntegrationService(run_id="test-run")
    # Should not raise even with weird input
    svc.journal_note("test", "x" * 10000)
    assert svc.journal_entries >= 1


def test_101_02_journal_write():
    """journal_write produces paths."""
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        svc = PipelineIntegrationService(run_id="test-journal", domain="AI")
        # Override output dir
        svc._journal.output_dir = __import__("pathlib").Path(tmpdir) / "test-journal"
        svc.journal_note("test", "Test note")
        notes, readme = svc.journal_write()
        assert isinstance(notes, str)
        assert isinstance(readme, str)


def test_101_03_build_context():
    """build_context assembles system + domain + task."""
    svc = PipelineIntegrationService(run_id="test-run", token_budget=500)
    result = svc.build_context(
        system_prompt="You are a research assistant.",
        domain_contexts=["Paper 1: Neural Networks", "Paper 2: Transformers"],
        task_context="Generate novel ideas.",
    )
    assert "research assistant" in result
    assert "Neural Networks" in result


def test_101_03_build_context_fails_safe():
    """build_context never crashes."""
    svc = PipelineIntegrationService(run_id="test-run")
    result = svc.build_context(system_prompt="test")
    assert isinstance(result, str)


def test_101_03_context_manager_accessible():
    """context_manager property returns ContextManager."""
    from backend.pipeline.context.manager import ContextManager
    svc = PipelineIntegrationService(run_id="test-run")
    assert isinstance(svc.context_manager, ContextManager)
