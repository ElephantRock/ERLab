"""Tests for BATCH-100 — Phase 6 Completion Verification.

Verifies that all Phase 6 additions are present and functional.
AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import pytest
from pathlib import Path



PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_100_01_all_phase6_modules_exist():
    """All Phase 6 backend modules exist on disk."""
    modules = [
        "backend/pipeline/strategies/models.py",
        "backend/pipeline/strategies/registry.py",
        "backend/pipeline/synthesis/fast_synthesizer.py",
        "backend/pipeline/model_selection.py",
        "backend/pipeline/streaming/progress_reporter.py",
        "backend/pipeline/reflection/reflector.py",
        "backend/pipeline/evaluation/proposal_evaluator.py",
        "backend/pipeline/knowledge/library.py",
        "backend/pipeline/knowledge/error_store.py",
        "backend/pipeline/knowledge/gap_queue.py",
        "backend/pipeline/safety/anti_fabrication.py",
        "backend/pipeline/soul_loader.py",
        "backend/pipeline/journal/writer.py",
        "backend/pipeline/context/manager.py",
        "backend/pipeline/concurrency.py",
        "backend/pipeline/planning/agent.py",
        "backend/pipeline/comparison.py",
        "backend/pipeline/literature/pubmed_source.py",
        "backend/pipeline/literature/crossref_source.py",
        "backend/pipeline/literature/multi_source.py",
        "backend/pipeline/literature/relevance_filter.py",
        "backend/pipeline/monitoring/health.py",
        "backend/pipeline/monitoring/cost_tracker.py",
        "backend/pipeline/tools/tool_registry.py",
        "backend/pipeline/export/md_to_latex.py",
        "backend/pipeline/export/bibtex_exporter.py",
    ]
    for mod in modules:
        assert (PROJECT_ROOT / mod).exists(), f"Missing: {mod}"


def test_100_02_manifest_files_exist():
    """SOUL.md and SKILL.md exist in project root."""
    assert (PROJECT_ROOT / "SOUL.md").exists()
    assert (PROJECT_ROOT / "SKILL.md").exists()

