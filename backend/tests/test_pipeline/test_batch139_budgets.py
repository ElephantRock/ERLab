"""BATCH-139 TASK-01: Externalize compaction budgets and paper limits."""

from __future__ import annotations

import json

import pytest

from backend.pipeline.compaction.budget_manager import (
    ContextBudgetManager,
    StageTokenBudget,
    _get_abstract_chars_loose,
    _get_abstract_chars_tight,
    _get_budgets_from_settings,
    _get_paper_limits_from_settings,
)


class TestBudgetDefaults:
    """TEST-139-01-01: Config has budget fields with correct defaults."""

    def test_budget_defaults_match_hardcoded(self) -> None:
        budgets = _get_budgets_from_settings()
        expected = {
            "gap_analysis": StageTokenBudget(base=6000, min_budget=3000, max_budget=10000),
            "idea_generation": StageTokenBudget(base=8000, min_budget=4000, max_budget=15000),
            "novelty_checking": StageTokenBudget(base=4000, min_budget=2000, max_budget=8000),
            "feasibility_scoring": StageTokenBudget(base=2000, min_budget=1000, max_budget=4000),
            "proposal_synthesis": StageTokenBudget(base=10000, min_budget=5000, max_budget=20000),
        }
        assert set(budgets.keys()) == set(expected.keys())
        for stage in expected:
            assert budgets[stage].base == expected[stage].base
            assert budgets[stage].min_budget == expected[stage].min_budget
            assert budgets[stage].max_budget == expected[stage].max_budget

    def test_budget_manager_uses_settings(self) -> None:
        mgr = ContextBudgetManager()
        assert "gap_analysis" in mgr._budgets
        assert mgr._budgets["gap_analysis"].base == 6000


class TestPaperLimits:
    """TEST-139-01-02: Paper limits read from settings."""

    def test_paper_limits_match_hardcoded(self) -> None:
        limits = _get_paper_limits_from_settings()
        expected = {
            "gap_analysis": 30,
            "idea_generation": 20,
            "novelty_checking": 10,
            "feasibility_scoring": 0,
            "proposal_synthesis": 15,
        }
        assert limits == expected

    def test_budget_manager_uses_paper_limits(self) -> None:
        mgr = ContextBudgetManager()
        assert mgr._paper_limits["gap_analysis"] == 30
        assert mgr._paper_limits["feasibility_scoring"] == 0


class TestAbstractChars:
    """TEST-139-01-03: Abstract char limits read from settings."""

    def test_abstract_chars_tight_default(self) -> None:
        assert _get_abstract_chars_tight() == 80

    def test_abstract_chars_loose_default(self) -> None:
        assert _get_abstract_chars_loose() == 150


class TestEnvOverride:
    """TEST-139-01-04: Budget override via env var works."""

    def test_env_override_budgets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        custom = json.dumps({
            "gap_analysis": {"base": 9999, "min_budget": 1000, "max_budget": 20000},
        })
        monkeypatch.setenv("EROCK_COMPACTION_STAGE_BUDGETS", custom)
        # Clear lru_cache so new settings are picked up
        from backend.config import get_settings
        get_settings.cache_clear()
        try:
            budgets = _get_budgets_from_settings()
            assert budgets["gap_analysis"].base == 9999
            assert budgets["gap_analysis"].min_budget == 1000
            assert budgets["gap_analysis"].max_budget == 20000
        finally:
            get_settings.cache_clear()

    def test_env_override_abstract_chars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EROCK_COMPACTION_ABSTRACT_CHARS_TIGHT", "50")
        monkeypatch.setenv("EROCK_COMPACTION_ABSTRACT_CHARS_LOOSE", "200")
        from backend.config import get_settings
        get_settings.cache_clear()
        try:
            assert _get_abstract_chars_tight() == 50
            assert _get_abstract_chars_loose() == 200
        finally:
            get_settings.cache_clear()


class TestMalformedJsonFallback:
    """TEST-139-01-05: Malformed budget JSON falls back to defaults."""

    def test_malformed_budget_json_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EROCK_COMPACTION_STAGE_BUDGETS", "{broken")
        from backend.config import get_settings
        get_settings.cache_clear()
        try:
            budgets = _get_budgets_from_settings()
            # Should fall back to hardcoded defaults
            assert budgets["gap_analysis"].base == 6000
            assert budgets["proposal_synthesis"].base == 10000
        finally:
            get_settings.cache_clear()

    def test_malformed_paper_limits_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EROCK_COMPACTION_PAPER_LIMITS", "not-json")
        from backend.config import get_settings
        get_settings.cache_clear()
        try:
            limits = _get_paper_limits_from_settings()
            assert limits["gap_analysis"] == 30
            assert limits["proposal_synthesis"] == 15
        finally:
            get_settings.cache_clear()
