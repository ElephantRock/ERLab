"""Fallback strategy presets aligned with ``pipeline.yaml``.

``pipeline.yaml`` is the production source of truth. These presets are used
only when YAML strategy loading is unavailable and therefore intentionally
mirror the four built-in YAML topologies. ``trimmer`` exists in the global
stage order but is not enabled by any current built-in strategy.
"""
from __future__ import annotations

from .models import PipelineStrategy, StageConfig, StrategyConfig
from .registry import StrategyRegistry


def _all_stages_enabled(**overrides: dict) -> dict[str, StageConfig]:
    """Return the 17 YAML strategy stages enabled, with optional overrides."""
    stage_names = [
        "literature_search",
        "ingestion",
        "gap_analysis",
        "gap_reflection",
        "idea_generation",
        "idea_reflection",
        "novelty_checking",
        "feasibility_scoring",
        "mechanical_metrics",
        "proposal_synthesis",
        "adversarial_review",
        "evaluation",
        "experiment_execution",  # Phase 5: opt-in, no-op unless experiment_spec_id in params
        "paper_synthesis",
        "citation_audit",
        "proposal_deepening",
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
    # Full proposal-to-paper topology; experiment_execution is opt-in at run time.
    registry.register(StrategyConfig(
        name=PipelineStrategy.DEEP_RESEARCH,
        stages=_all_stages_enabled(
            literature_search=StageConfig(enabled=True, params={"citation_explore": True}),
        ),
        max_total_time=1800.0,
        description=(
            "Full proposal-to-paper pipeline: literature search, ingestion, gap analysis, "
            "idea generation, novelty checking, feasibility scoring, metrics, proposal "
            "synthesis, adversarial review/evaluation, optional experiment execution, "
            "paper synthesis, citation audit, proposal deepening, and export."
        ),
    ))

    # ── FAST SCAN ─────────────────────────────────────────
    # Keeps lightweight idea generation so feasibility and concise synthesis
    # are reachable, while skipping tree search and expensive assurance stages.
    registry.register(StrategyConfig(
        name=PipelineStrategy.FAST_SCAN,
        stages=_all_stages_enabled(
            idea_generation=StageConfig(enabled=True),
            novelty_checking=StageConfig(enabled=False),
            mechanical_metrics=StageConfig(enabled=False),
            adversarial_review=StageConfig(enabled=False, params={"enabled": False}),
            evaluation=StageConfig(enabled=False),
            gap_reflection=StageConfig(enabled=False),
            idea_reflection=StageConfig(enabled=False),
            paper_synthesis=StageConfig(enabled=False, params={"enabled": False}),
            citation_audit=StageConfig(enabled=False),
            experiment_execution=StageConfig(enabled=False),
            proposal_deepening=StageConfig(enabled=False),
        ),
        max_total_time=300.0,
        description=(
            "Quick scan: literature search, ingestion, gap analysis, "
            "lightweight idea generation, feasibility scoring, concise synthesis, "
            "and export. Skips tree search, novelty checking, metrics, adversarial "
            "review, paper synthesis, and citation audit."
        ),
    ))

    # ── ACADEMIC PROPOSAL ─────────────────────────────────
    # Current production topology is intentionally identical to deep_research.
    # The distinct product label is preserved; no inactive threshold/timeout
    # semantics are advertised in the fallback preset.
    registry.register(StrategyConfig(
        name=PipelineStrategy.ACADEMIC_PROPOSAL,
        stages=_all_stages_enabled(
            literature_search=StageConfig(enabled=True, params={"citation_explore": True}),
        ),
        max_total_time=1800.0,
        description=(
            "Academic proposal-to-paper workflow. Current production stage "
            "topology matches deep_research: reflection, novelty/feasibility, "
            "proposal review/evaluation, optional experiment execution, paper "
            "synthesis, citation audit, deepening, and export."
        ),
    ))

    # ── LITERATURE REVIEW ─────────────────────────────────
    # Only runs through gap_analysis, then exports. No idea generation.
    # Citation audit OFF (no proposals to audit).
    registry.register(StrategyConfig(
        name=PipelineStrategy.LITERATURE_REVIEW,
        stages=_all_stages_enabled(
            idea_generation=StageConfig(enabled=False),
            novelty_checking=StageConfig(enabled=False),
            feasibility_scoring=StageConfig(enabled=False),
            mechanical_metrics=StageConfig(enabled=False),
            proposal_synthesis=StageConfig(enabled=False),
            adversarial_review=StageConfig(enabled=False),
            evaluation=StageConfig(enabled=False),
            gap_reflection=StageConfig(enabled=False),
            idea_reflection=StageConfig(enabled=False),
            paper_synthesis=StageConfig(enabled=False, params={"enabled": False}),
            citation_audit=StageConfig(enabled=False),
            proposal_deepening=StageConfig(enabled=False),
            experiment_execution=StageConfig(enabled=False),
        ),
        max_total_time=600.0,
        description=(
            "Literature review only: search, ingest, analyze gaps, then export. "
            "No idea generation, proposal synthesis, or citation audit. ~10 minutes."
        ),
    ))
