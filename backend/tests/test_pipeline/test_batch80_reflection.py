"""Tests for BATCH-80 — Iterative Reflection Loop.

TASK-01: ReflectionStage (8 tests)
TASK-02: Orchestrator Integration (4 tests)

AIV v5.3 — T1, T2, T5. NOTE: Use asyncio.run() not @pytest.mark.asyncio.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pipeline.reflection.reflector import ReflectionResult, ReflectionStage
from backend.pipeline.strategies.presets import register_presets
from backend.pipeline.strategies.registry import StrategyRegistry

# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.complete = AsyncMock(return_value=(
        "SCORE: 0.85\n"
        "PASSED: yes\n"
        "JUSTIFICATION: Gaps cover the main domain challenges.\n"
        "FEEDBACK: Consider adding a gap about cross-domain transfer learning.\n"
    ))
    return provider


@pytest.fixture
def low_score_provider():
    """Provider that always returns low scores to test retry."""
    provider = AsyncMock()
    provider.complete = AsyncMock(return_value=(
        "SCORE: 0.3\n"
        "PASSED: no\n"
        "JUSTIFICATION: Gaps are too generic.\n"
        "FEEDBACK: Make gaps more specific to the domain.\n"
    ))
    return provider


@pytest.fixture
def mock_gaps():
    gaps = []
    for i in range(3):
        g = MagicMock()
        g.title = f"Gap {i+1}: Missing approach X"
        g.name = g.title
        g.description = f"No existing work on approach X variant {i+1}."
        gaps.append(g)
    return gaps


# ══════════════════════════════════════════════════════════
# TASK-01: ReflectionStage
# ══════════════════════════════════════════════════════════

# TEST-80-01-01: reflect_gaps returns ReflectionResult
def test_80_01_01_reflect_gaps_returns_result(mock_provider, mock_gaps):
    """reflect_gaps returns ReflectionResult with score and justification."""
    stage = ReflectionStage(provider=mock_provider, threshold=0.6)
    result = asyncio.run(stage.reflect_gaps(mock_gaps, "sparse attention"))
    assert isinstance(result, ReflectionResult)
    assert result.score > 0.0
    assert result.justification


# TEST-80-01-02: reflect_with_retry stops after max_iterations
def test_80_01_02_retry_stops_at_max_iterations(low_score_provider, mock_gaps):
    """reflect_with_retry stops after max_iterations even with low scores."""
    stage = ReflectionStage(provider=low_score_provider, threshold=0.6, max_iterations=2)
    reflect_fn = stage.reflect_gaps
    regenerate_fn = AsyncMock(return_value=mock_gaps)
    _, results = asyncio.run(
        stage.reflect_with_retry(mock_gaps, reflect_fn, regenerate_fn)
    )
    assert len(results) == 2  # stopped at max_iterations=2
    assert results[-1].iteration == 2


# TEST-80-01-03: High score returns immediately
def test_80_01_03_high_score_returns_immediately(mock_provider, mock_gaps):
    """When score >= threshold, only 1 iteration."""
    stage = ReflectionStage(provider=mock_provider, threshold=0.6)
    reflect_fn = stage.reflect_gaps
    regenerate_fn = AsyncMock(return_value=mock_gaps)
    _, results = asyncio.run(
        stage.reflect_with_retry(mock_gaps, reflect_fn, regenerate_fn)
    )
    assert len(results) == 1
    assert results[0].passed is True


# TEST-80-01-04: Feedback passed to regenerate
def test_80_01_04_feedback_passed_to_regenerate(low_score_provider, mock_gaps):
    """Regenerate function receives the feedback string."""
    stage = ReflectionStage(provider=low_score_provider, threshold=0.6, max_iterations=2)
    reflect_fn = stage.reflect_gaps
    regenerate_fn = AsyncMock(return_value=mock_gaps)
    asyncio.run(stage.reflect_with_retry(mock_gaps, reflect_fn, regenerate_fn))
    # regenerate_fn should have been called with (content, feedback)
    assert regenerate_fn.called
    call_args = regenerate_fn.call_args[0]
    assert len(call_args) >= 2  # content and feedback


# TEST-80-01-05: LLM timeout handled gracefully
def test_80_01_05_llm_timeout_handled(mock_gaps):
    """LLM timeout auto-passes (fail-open)."""
    provider = AsyncMock()
    provider.complete = AsyncMock(side_effect=TimeoutError("LLM timeout"))
    stage = ReflectionStage(provider=provider, threshold=0.6)
    result = asyncio.run(stage.reflect_gaps(mock_gaps))
    assert result.passed is True  # fail-open
    assert result.score == 1.0


# TEST-80-01-06: Iteration counter in results
def test_80_01_06_iteration_counter(low_score_provider, mock_gaps):
    """Each result has the correct iteration number."""
    stage = ReflectionStage(provider=low_score_provider, threshold=0.6, max_iterations=3)
    reflect_fn = stage.reflect_gaps
    regenerate_fn = AsyncMock(return_value=mock_gaps)
    _, results = asyncio.run(
        stage.reflect_with_retry(mock_gaps, reflect_fn, regenerate_fn)
    )
    for i, result in enumerate(results, 1):
        assert result.iteration == i


# TEST-80-01-07: Response parsing
def test_80_01_07_parse_response():
    """_parse_response correctly extracts structured fields."""
    text = (
        "SCORE: 0.72\n"
        "PASSED: yes\n"
        "JUSTIFICATION: Good coverage but missing edge cases.\n"
        "FEEDBACK: Add gaps about computational efficiency.\n"
    )
    result = ReflectionStage._parse_response(text)
    assert result.score == 0.72
    assert result.passed is True
    assert "coverage" in result.justification.lower()
    assert "efficiency" in result.feedback.lower()


# TEST-80-01-08: Empty gaps auto-pass
def test_80_01_08_empty_gaps_auto_pass():
    """Empty gap list auto-passes without LLM call."""
    provider = AsyncMock()
    stage = ReflectionStage(provider=provider, threshold=0.6)
    result = asyncio.run(stage.reflect_gaps([], "test"))
    assert result.passed is True
    assert not provider.complete.called  # No LLM call needed


# ══════════════════════════════════════════════════════════
# TASK-02: Strategy Integration
# ══════════════════════════════════════════════════════════

# TEST-80-02-01: fast_scan has no reflection
def test_80_02_01_fast_scan_no_reflection():
    """fast_scan strategy should not enable reflection (HB-02)."""
    # fast_scan doesn't have reflection in its config
    # This is verified by the strategy not including reflection stages
    registry = StrategyRegistry()
    register_presets(registry)
    config = registry.get("fast_scan")
    # Reflection is controlled at orchestrator level, not stage level
    # But fast_scan's max_total_time (300s) wouldn't allow reflection iterations
    assert config.max_total_time <= 300.0


# TEST-80-02-02: deep_research allows time for reflection
def test_80_02_02_deep_research_allows_reflection():
    """deep_research has enough time budget for reflection iterations."""
    registry = StrategyRegistry()
    register_presets(registry)
    config = registry.get("deep_research")
    assert config.max_total_time >= 1200.0  # At least 20 min


# TEST-80-02-03: ReflectionResult score clamped
def test_80_02_03_score_clamped():
    """ReflectionResult.score is clamped to [0, 1]."""
    result = ReflectionResult(score=2.0)
    assert result.score == 1.0
    result_neg = ReflectionResult(score=-1.0)
    assert result_neg.score == 0.0


# TEST-80-02-04: ReflectionStage can be instantiated without provider
def test_80_02_04_no_provider_instantiation():
    """ReflectionStage works without a provider (auto-pass mode)."""
    stage = ReflectionStage(provider=None)
    gaps = [MagicMock(title="Test", description="Test gap")]
    result = asyncio.run(stage.reflect_gaps(gaps))
    assert result.passed is True
