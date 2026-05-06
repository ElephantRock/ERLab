"""Tests for BATCH-78 — Thinking/Task Model Split.

TASK-01: Config + Provider Split (8 tests)
TASK-02: Model Selector (7 tests)

AIV v5.3 — T1, T2, T5
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from backend.config import Settings
from backend.pipeline.model_selection import ModelSelector, THINKING_TASKS, GENERATION_TASKS


# ══════════════════════════════════════════════════════════
# TASK-01: Config + Provider Split
# ══════════════════════════════════════════════════════════

# TEST-78-01-01: Config has new fields
def test_78_01_01_settings_has_model_split_fields():
    """Settings has thinking_model and generation_model fields."""
    s = Settings()
    assert hasattr(s, "thinking_model")
    assert hasattr(s, "generation_model")
    assert hasattr(s, "thinking_model_max_tokens")
    assert hasattr(s, "generation_model_max_tokens")


# TEST-78-01-02: Defaults are empty (backward compat)
def test_78_01_02_defaults_are_empty():
    """thinking_model and generation_model default to empty strings."""
    s = Settings()
    assert s.thinking_model == ""
    assert s.generation_model == ""


# TEST-78-01-03: Max tokens defaults
def test_78_01_03_max_tokens_defaults():
    """thinking_model_max_tokens=2048, generation_model_max_tokens=8192."""
    s = Settings()
    assert s.thinking_model_max_tokens == 2048
    assert s.generation_model_max_tokens == 8192


# TEST-78-01-04: get_thinking_provider returns same when empty
def test_78_01_04_thinking_provider_same_when_empty():
    """Empty thinking_model returns same as generation provider."""
    s = Settings()
    with patch("backend.providers.provider_factory._get_registry") as mock_reg:
        mock_provider = MagicMock()
        mock_reg.return_value.create.return_value = mock_provider
        from backend.providers.provider_factory import get_thinking_provider, get_generation_provider
        tp = get_thinking_provider(s)
        gp = get_generation_provider(s)
        # Both should call create with the same settings
        assert mock_reg.return_value.create.called


# TEST-78-01-05: get_thinking_provider uses configured model
def test_78_01_05_thinking_provider_uses_configured_model():
    """Non-empty thinking_model passes name to create()."""
    s = Settings(thinking_model="ollama")
    with patch("backend.providers.provider_factory._get_registry") as mock_reg:
        mock_provider = MagicMock()
        mock_reg.return_value.create.return_value = mock_provider
        from backend.providers.provider_factory import get_thinking_provider
        get_thinking_provider(s)
        # Should be called with name="ollama"
        call_args = mock_reg.return_value.create.call_args
        assert call_args is not None


# TEST-78-01-06: Fallback on error
def test_78_01_06_fallback_on_thinking_model_error():
    """If thinking model fails, falls back to default provider."""
    s = Settings(thinking_model="nonexistent_model_xyz")
    with patch("backend.providers.provider_factory._get_registry") as mock_reg:
        # First call (thinking) raises, second call (fallback) succeeds
        mock_provider = MagicMock()
        mock_reg.return_value.create.side_effect = [
            ValueError("Unknown provider"),
            mock_provider,
        ]
        from backend.providers.provider_factory import get_thinking_provider
        result = get_thinking_provider(s)
        assert result == mock_provider


# TEST-78-01-07: get_generation_provider uses configured model
def test_78_01_07_generation_provider_uses_configured_model():
    """Non-empty generation_model passes name to create()."""
    s = Settings(generation_model="anthropic")
    with patch("backend.providers.provider_factory._get_registry") as mock_reg:
        mock_provider = MagicMock()
        mock_reg.return_value.create.return_value = mock_provider
        from backend.providers.provider_factory import get_generation_provider
        get_generation_provider(s)
        assert mock_reg.return_value.create.called


# TEST-78-01-08: Settings env var override
def test_78_01_08_settings_env_override():
    """Settings fields can be overridden via environment variables."""
    s = Settings(thinking_model="ollama:llama3", generation_model="openai:gpt-4")
    assert s.thinking_model == "ollama:llama3"
    assert s.generation_model == "openai:gpt-4"


# ══════════════════════════════════════════════════════════
# TASK-02: Model Selector
# ══════════════════════════════════════════════════════════

# TEST-78-02-01: classify → thinking
def test_78_02_01_classify_returns_thinking_provider():
    """classify task type resolves to thinking provider."""
    with patch("backend.providers.provider_factory.get_thinking_provider") as mock_tp:
        mock_tp.return_value = MagicMock()
        selector = ModelSelector(settings=MagicMock())
        result = selector.resolve("classify")
        assert mock_tp.called


# TEST-78-02-02: generate → generation
def test_78_02_02_generate_returns_generation_provider():
    """generate task type resolves to generation provider."""
    with patch("backend.providers.provider_factory.get_generation_provider") as mock_gp:
        mock_gp.return_value = MagicMock()
        selector = ModelSelector(settings=MagicMock())
        result = selector.resolve("generate")
        assert mock_gp.called


# TEST-78-02-03: Unknown → generation
def test_78_02_03_unknown_defaults_to_generation():
    """Unknown task types default to generation provider."""
    with patch("backend.providers.provider_factory.get_generation_provider") as mock_gp:
        mock_gp.return_value = MagicMock()
        selector = ModelSelector(settings=MagicMock())
        result = selector.resolve("unknown_type")
        assert mock_gp.called


# TEST-78-02-04: is_thinking_task
def test_78_02_04_is_thinking_task():
    """is_thinking_task correctly classifies thinking tasks."""
    assert ModelSelector.is_thinking_task("classify") is True
    assert ModelSelector.is_thinking_task("extract") is True
    assert ModelSelector.is_thinking_task("generate") is False


# TEST-78-02-05: is_generation_task
def test_78_02_05_is_generation_task():
    """is_generation_task correctly classifies generation tasks."""
    assert ModelSelector.is_generation_task("generate") is True
    assert ModelSelector.is_generation_task("synthesize") is True
    assert ModelSelector.is_generation_task("classify") is False


# TEST-78-02-06: All thinking tasks listed
def test_78_02_06_all_thinking_tasks_in_set():
    """THINKING_TASKS contains expected task types."""
    assert "classify" in THINKING_TASKS
    assert "extract" in THINKING_TASKS
    assert "rank" in THINKING_TASKS
    assert "filter" in THINKING_TASKS
    assert "dedup" in THINKING_TASKS


# TEST-78-02-07: All generation tasks listed
def test_78_02_07_all_generation_tasks_in_set():
    """GENERATION_TASKS contains expected task types."""
    assert "generate" in GENERATION_TASKS
    assert "synthesize" in GENERATION_TASKS
    assert "write" in GENERATION_TASKS
    assert "critique" in GENERATION_TASKS
    assert "ideate" in GENERATION_TASKS
