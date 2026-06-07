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