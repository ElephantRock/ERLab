"""Tests for BATCH-76/TASK-01 — Strategy Models + Registry.

AIV v5.3 Test Integrity Protocol:
  - T1 (falsifiable): Every test has a Falsified By description
  - T2 (coverage): Happy path + error path + boundary conditions
  - T5 (traceability): Each test maps to an AC
  - T6 (falsification): Critical priority task — mandatory falsification
"""
from __future__ import annotations

import json
import pytest

from backend.pipeline.strategies.models import (
    PipelineStrategy,
    StageConfig,
    StrategyConfig,
)
from backend.pipeline.strategies.registry import StrategyRegistry
from backend.pipeline.strategies.presets import register_presets


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def empty_registry() -> StrategyRegistry:
    """Registry with no presets registered."""
    return StrategyRegistry()


@pytest.fixture
def registry() -> StrategyRegistry:
    """Registry with all 4 presets loaded."""
    r = StrategyRegistry()
    register_presets(r)
    return r


# ── TEST-76-01-01: Registry returns correct config ───────
# AC-01-02

def test_76_01_01_registry_returns_correct_strategy_config(registry):
    """StrategyRegistry.get() returns StrategyConfig with correct PipelineStrategy."""
    config = registry.get("deep_research")
    assert config.name == PipelineStrategy.DEEP_RESEARCH


# ── TEST-76-01-02: All 4 strategies pre-registered ──────
# AC-01-01, AC-01-03

def test_76_01_02_all_four_strategies_registered(registry):
    """All 4 strategies are available after register_presets()."""
    all_configs = registry.list_all()
    assert len(all_configs) == 4
    names = {c.name.value for c in all_configs}
    assert names == {"fast_scan", "deep_research", "academic_proposal", "literature_review"}


def test_76_01_02b_empty_registry_has_no_presets(empty_registry):
    """Without register_presets(), registry has no strategies."""
    assert len(empty_registry.list_all()) == 0


# ── TEST-76-01-03: StageConfig defaults ──────────────────
# Boundary test for default values

def test_76_01_03_stage_config_defaults():
    """StageConfig defaults to enabled=True and timeout=300.0."""
    sc = StageConfig()
    assert sc.enabled is True
    assert sc.timeout == 300.0
    assert sc.params == {}


# ── TEST-76-01-04: deep_research enables core production stages ───────
# AC-01-05

def test_76_01_04_deep_research_has_all_stages(registry):
    """deep_research fallback enables the core production stages."""
    config = registry.get("deep_research")
    expected_stages = [
        "literature_search", "ingestion", "gap_analysis",
        "idea_generation", "novelty_checking", "feasibility_scoring",
        "mechanical_metrics", "proposal_synthesis", "export",
    ]
    for stage_name in expected_stages:
        assert stage_name in config.stages, f"Missing stage: {stage_name}"
        assert config.stages[stage_name].enabled is True, (
            f"Stage {stage_name} should be enabled in deep_research"
        )


# ── TEST-76-01-05: StrategyConfig serialization round-trip ─
# AC-01-06

def test_76_01_05_strategy_config_round_trip():
    """StrategyConfig.to_dict() → from_dict() produces equal config."""
    original = StrategyConfig(
        name=PipelineStrategy.FAST_SCAN,
        stages={
            "ingestion": StageConfig(enabled=True, timeout=120.0),
            "idea_generation": StageConfig(enabled=False),
        },
        max_total_time=300.0,
        description="test",
    )
    serialized = original.to_dict()
    # Verify JSON-serializable
    json_str = json.dumps(serialized)
    assert isinstance(json_str, str)

    # Round-trip
    restored = StrategyConfig.from_dict(json.loads(json_str))
    assert restored.name == original.name
    assert restored.max_total_time == original.max_total_time
    assert restored.description == original.description
    assert "ingestion" in restored.stages
    assert restored.stages["ingestion"].timeout == 120.0
    assert restored.stages["idea_generation"].enabled is False


# ── TEST-76-01-06: Custom strategy registration ─────────

def test_76_01_06_custom_strategy_registered_and_retrieved(empty_registry):
    """Custom strategies can be registered and retrieved."""
    custom = StrategyConfig(
        name=PipelineStrategy.FAST_SCAN,  # reuse enum, custom description
        stages={"literature_search": StageConfig()},
        description="custom test",
    )
    empty_registry.register(custom)
    result = empty_registry.get("fast_scan")
    assert result.description == "custom test"


def test_76_01_06b_register_overwrites(empty_registry):
    """Registering the same name overwrites the previous config."""
    v1 = StrategyConfig(
        name=PipelineStrategy.FAST_SCAN,
        description="version 1",
    )
    v2 = StrategyConfig(
        name=PipelineStrategy.FAST_SCAN,
        description="version 2",
    )
    empty_registry.register(v1)
    empty_registry.register(v2)
    assert empty_registry.get("fast_scan").description == "version 2"


# ── TEST-76-01-07: fast_scan disables correct stages ────
# AC-01-04

def test_76_01_07_fast_scan_disables_expensive_stages(registry):
    """fast_scan keeps lightweight ideation but disables expensive scoring/review stages."""
    config = registry.get("fast_scan")
    # Lightweight ideation is required so feasibility + concise synthesis are reachable.
    assert config.stages["idea_generation"].enabled is True
    # These should be DISABLED
    assert config.stages["novelty_checking"].enabled is False
    assert config.stages["mechanical_metrics"].enabled is False
    # These should be ENABLED
    assert config.stages["literature_search"].enabled is True
    assert config.stages["ingestion"].enabled is True
    assert config.stages["gap_analysis"].enabled is True
    assert config.stages["feasibility_scoring"].enabled is True
    assert config.stages["proposal_synthesis"].enabled is True
    assert config.stages["export"].enabled is True


# ── TEST-76-01-08: Invalid strategy raises ValueError ───
# Error path — AC-01-02

def test_76_01_08_invalid_strategy_raises_value_error(registry):
    """Getting an unregistered strategy raises ValueError."""
    with pytest.raises(ValueError, match="Unknown pipeline strategy"):
        registry.get("nonexistent")


def test_76_01_08b_error_message_lists_valid_strategies(registry):
    """ValueError message includes the list of valid strategy names."""
    with pytest.raises(ValueError, match="deep_research") as exc_info:
        registry.get("bad_name")
    assert "fast_scan" in str(exc_info.value)


# ── Additional coverage tests ────────────────────────────

def test_literature_review_disables_generation_stages(registry):
    """literature_review disables idea generation, scoring, synthesis."""
    config = registry.get("literature_review")
    disabled = ["idea_generation", "novelty_checking", "feasibility_scoring",
                "mechanical_metrics", "proposal_synthesis"]
    for name in disabled:
        assert config.stages[name].enabled is False, f"{name} should be disabled"
    # Should still have search, ingestion, gap_analysis, export
    assert config.stages["literature_search"].enabled is True
    assert config.stages["export"].enabled is True


def test_academic_proposal_matches_deep_runtime_topology(registry):
    """Fallback presets must not advertise inactive threshold/timeout semantics."""
    academic = registry.get("academic_proposal")
    deep = registry.get("deep_research")
    academic_enabled = {k for k, v in academic.stages.items() if v.enabled}
    deep_enabled = {k for k, v in deep.stages.items() if v.enabled}
    assert academic_enabled == deep_enabled
    assert academic.max_total_time == deep.max_total_time
    assert academic.stages["novelty_checking"].params.get("threshold") is None
    assert academic.stages["proposal_synthesis"].timeout == deep.stages["proposal_synthesis"].timeout


def test_registry_has_utility_methods(registry):
    """Registry has has() and clear() methods."""
    assert registry.has("deep_research") is True
    assert registry.has("nonexistent") is False
    registry.clear()
    assert len(registry.list_all()) == 0
