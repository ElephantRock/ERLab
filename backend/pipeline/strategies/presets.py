"""Default strategy presets matching _STAGE_ORDER in orchestrator.py.

Actual stage names (from PipelineOrchestrator._STAGE_ORDER):
  0. literature_search
  1. ingestion
  2. gap_analysis
  3. idea_generation
  4. novelty_checking
  5. feasibility_scoring
  6. mechanical_metrics
  7. proposal_synthesis
  8. export
"""
from __future__ import annotations

from .models import PipelineStrategy, StageConfig, StrategyConfig
from .registry import StrategyRegistry


def _all_stages_enabled(**overrides: dict) -> dict[str, StageConfig]:
    """Return all 9 stages enabled with optional per-stage overrides."""
    stage_names = [
        "literature_search",
        "ingestion",
        "gap_analysis",
        "idea_generation",
        "novelty_checking",
        "feasibility_scoring",
        "mechanical_metrics",
        "proposal_synthesis",
        "export",
    ]
    stages = {}
    for name in stage_names:
        if name in overrides:
            stages[name] = overrides[name]
        else:
            stages[name] = StageConfig()
    return stages


def register_presets(registry: StrategyRegistry) -> None:
    """Register the four built-in strategy presets."""

    # ── DEEP RESEARCH ─────────────────────────────────────
    # All 9 stages enabled. This is the current pipeline behavior.
    registry.register(StrategyConfig(
        name=PipelineStrategy.DEEP_RESEARCH,
        stages=_all_stages_enabled(),
        max_total_time=1800.0,
        description=(
            "Full pipeline: literature search, ingestion, gap analysis, "
            "idea generation with tree search, novelty checking, feasibility "
            "scoring, metrics, proposal synthesis, and export. ~25 minutes."
        ),
    ))

    # ── FAST SCAN ─────────────────────────────────────────
    # Skips expensive stages: idea_generation (tree search),
    # novelty_checking, and mechanical_metrics.
    # Runs: literature_search, ingestion, gap_analysis,
    #        feasibility_scoring, proposal_synthesis, export
    registry.register(StrategyConfig(
        name=PipelineStrategy.FAST_SCAN,
        stages=_all_stages_enabled(
            idea_generation=StageConfig(enabled=False),
            novelty_checking=StageConfig(enabled=False),
            mechanical_metrics=StageConfig(enabled=False),
        ),
        max_total_time=300.0,
        description=(
            "Quick scan: literature search, ingestion, gap analysis, "
            "feasibility scoring, light synthesis, and export. "
            "Skips tree search, novelty checking, and metrics. ~2-5 minutes."
        ),
    ))

    # ── ACADEMIC PROPOSAL ─────────────────────────────────
    # Like deep_research but with longer timeouts and stricter scoring.
    registry.register(StrategyConfig(
        name=PipelineStrategy.ACADEMIC_PROPOSAL,
        stages=_all_stages_enabled(
            novelty_checking=StageConfig(timeout=600.0, params={"threshold": 0.7}),
            feasibility_scoring=StageConfig(timeout=600.0, params={"threshold": 0.7}),
            proposal_synthesis=StageConfig(timeout=900.0),
        ),
        max_total_time=3600.0,
        description=(
            "Academic-grade proposal: full pipeline with longer timeouts "
            "and stricter novelty/feasibility thresholds. ~45 minutes."
        ),
    ))

    # ── LITERATURE REVIEW ─────────────────────────────────
    # Only runs through gap_analysis, then exports. No idea generation.
    registry.register(StrategyConfig(
        name=PipelineStrategy.LITERATURE_REVIEW,
        stages=_all_stages_enabled(
            idea_generation=StageConfig(enabled=False),
            novelty_checking=StageConfig(enabled=False),
            feasibility_scoring=StageConfig(enabled=False),
            mechanical_metrics=StageConfig(enabled=False),
            proposal_synthesis=StageConfig(enabled=False),
        ),
        max_total_time=600.0,
        description=(
            "Literature review only: search, ingest, analyze gaps, then export. "
            "No idea generation or proposal synthesis. ~10 minutes."
        ),
    ))
