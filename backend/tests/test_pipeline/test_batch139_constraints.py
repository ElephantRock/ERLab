"""BATCH-139 TASK-02: Externalize constraint config."""

from __future__ import annotations

import pytest

from backend.pipeline.self_improve.constraints import ConstraintConfig


class TestConstraintDefaults:
    """TEST-139-02-01: Config has constraint fields with defaults."""

    def test_settings_has_constraint_fields(self) -> None:
        from backend.config import Settings
        s = Settings(_env_file=None)
        assert s.constraint_max_size == 5000
        assert s.constraint_max_growth_pct == 0.3
        assert s.constraint_min_sections == 3
        assert s.constraint_allow_empty is False


class TestSettingsRead:
    """TEST-139-02-02: ConstraintConfig built from settings, not literals."""

    def test_constraint_config_from_settings(self) -> None:
        from backend.config import Settings
        s = Settings(_env_file=None)
        cfg = ConstraintConfig(
            max_size=s.constraint_max_size,
            max_growth_pct=s.constraint_max_growth_pct,
            allow_empty=s.constraint_allow_empty,
            min_sections=s.constraint_min_sections,
        )
        assert cfg.max_size == 5000
        assert cfg.max_growth_pct == pytest.approx(0.3)
        assert cfg.allow_empty is False
        assert cfg.min_sections == 3


class TestConstraintEnvOverride:
    """TEST-139-02-03: Constraint override via env var works."""

    def test_env_override_max_size(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EROCK_CONSTRAINT_MAX_SIZE", "10000")
        monkeypatch.setenv("EROCK_CONSTRAINT_MAX_GROWTH_PCT", "0.5")
        monkeypatch.setenv("EROCK_CONSTRAINT_MIN_SECTIONS", "5")
        monkeypatch.setenv("EROCK_CONSTRAINT_ALLOW_EMPTY", "true")
        from backend.config import Settings
        s_env = Settings()
        assert s_env.constraint_max_size == 10000
        assert s_env.constraint_max_growth_pct == pytest.approx(0.5)
        assert s_env.constraint_min_sections == 5
        assert s_env.constraint_allow_empty is True
