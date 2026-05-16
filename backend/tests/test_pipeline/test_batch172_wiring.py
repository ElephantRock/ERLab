"""BATCH-172 TASK-01: Wire 3 Dead Stages into Orchestrator.

Verify GapReflectionStage, IdeaReflectionStage, and EvaluationStage
are wired into PipelineOrchestrator._build_stages() at the correct positions.
"""
from __future__ import annotations

import asyncio
import importlib
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper: build an orchestrator with heavy mocking (no real LLM / DB calls)
# ---------------------------------------------------------------------------

def _make_orchestrator():
    """Create a PipelineOrchestrator with all external deps mocked.

    Uses __new__ to skip __init__ entirely and manually sets the
    attributes that _build_stages() needs.
    """
    from backend.pipeline.orchestrator import PipelineOrchestrator

    prov = MagicMock()
    prov.provider_name = "mock"
    s = MagicMock()
    s.lmstudio_enabled = False
    s.thinking_model = ""
    s.tree_of_thought_enabled = False

    orch = PipelineOrchestrator.__new__(PipelineOrchestrator)
    # Minimal init to make _build_stages work
    orch._provider = prov
    orch._thinking_provider = None
    orch._settings = s
    orch._hooks = MagicMock()
    orch._agent = MagicMock()
    orch._gap_analyzer = MagicMock()
    orch._goal_manager = MagicMock()
    orch._memory = MagicMock()
    orch._faithfulness_checker = MagicMock()
    orch._search = MagicMock()
    orch._store = MagicMock()
    orch._bm25 = MagicMock()
    orch._embedding = MagicMock()
    orch._kg = None
    orch._novelty = MagicMock()
    orch._feasibility = MagicMock()
    orch._export = MagicMock()
    orch._dag_executor = None
    orch._dag_agents = None
    orch._forest = None
    orch._reasoning_verifier = None
    orch._synthesizer = MagicMock()
    orch._model_selector = None
    orch._strategy_name = "deep_research"
    orch._governance_validator = None
    orch._governance_audit = None
    return orch


# ── Test 1: _build_stages returns 17 stages ────────────────────────────

def test_build_stages_returns_17():
    orch = _make_orchestrator()
    stages = orch._build_stages()
    assert len(stages) == 17, f"Expected 17 stages, got {len(stages)}"


# ── Test 2: Stage names match _STAGE_ORDER exactly ─────────────────────

def test_stage_names_match_order():
    from backend.pipeline.orchestrator import PipelineOrchestrator
    orch = _make_orchestrator()
    stages = orch._build_stages()
    names = [s.name for s in stages]
    assert names == list(PipelineOrchestrator._STAGE_ORDER), (
        f"Stage names mismatch.\n  Got:      {names}\n  Expected: {PipelineOrchestrator._STAGE_ORDER}"
    )


# ── Test 3: gap_reflection at index 3 ──────────────────────────────────

def test_gap_reflection_at_index_4():
    orch = _make_orchestrator()
    stages = orch._build_stages()
    assert stages[4].name == "gap_reflection", f"Index 4 is '{stages[4].name}', expected 'gap_reflection'"


# ── Test 4: idea_reflection at index 5 ─────────────────────────────────

def test_idea_reflection_at_index_6():
    orch = _make_orchestrator()
    stages = orch._build_stages()
    assert stages[6].name == "idea_reflection", f"Index 6 is '{stages[6].name}', expected 'idea_reflection'"


# ── Test 5: evaluation at index 11 ─────────────────────────────────────

def test_evaluation_at_index_12():
    orch = _make_orchestrator()
    stages = orch._build_stages()
    assert stages[12].name == "evaluation", f"Index 12 is '{stages[12].name}', expected 'evaluation'"


# ── Test 6: Reflection stages use thinking_provider (with fallback) ────

def test_reflection_stages_use_thinking_provider():
    """When _thinking_provider is None, stages should use self._provider as fallback."""
    orch = _make_orchestrator()
    # _thinking_provider is None, so fallback is self._provider
    stages = orch._build_stages()
    gap_ref = stages[4]
    idea_ref = stages[6]
    # Both should have received the provider
    assert gap_ref._provider is orch._provider
    assert idea_ref._provider is orch._provider

    # Now test with thinking_provider set
    mock_tp = MagicMock()
    mock_tp.provider_name = "thinking_mock"
    orch._thinking_provider = mock_tp
    stages2 = orch._build_stages()
    assert stages2[4]._provider is mock_tp
    assert stages2[6]._provider is mock_tp


# ── Test 7: Orchestrator.__init__() succeeds (no import/init error) ────

def test_orchestrator_import_succeeds():
    """Verify the orchestrator module imports cleanly with new stages."""
    import backend.pipeline.orchestrator as orch_mod
    assert hasattr(orch_mod, "PipelineOrchestrator")
    assert hasattr(orch_mod.PipelineOrchestrator, "_build_stages")
    assert hasattr(orch_mod.PipelineOrchestrator, "_STAGE_ORDER")
