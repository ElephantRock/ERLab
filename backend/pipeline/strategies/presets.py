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
  8. adversarial_review
  9. paper_synthesis
  10. citation_audit
  11. proposal_deepening
  12. export
"""
from __future__ import annotations

from .models import PipelineStrategy, StageConfig, StrategyConfig
from .registry import StrategyRegistry


def _all_stages_enabled(**overrides: dict) -> dict[str, StageConfig]:
    """Return all 13 stages enabled with optional per-stage overrides."""
    stage_names = [
        "literature_search",
        "ingestion",
        "gap_analysis",
        "idea_generation",
        "novelty_checking",
        "feasibility_scoring",
        "mechanical_metrics",
        "proposal_synthesis",
        "adversarial_review",
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
    # All 13 stages enabled. Adversarial review ON. Paper synthesis ON.
    # Citation audit ON.
    registry.register(StrategyConfig(
        name=PipelineStrategy.DEEP_RESEARCH,
        stages=_all_stages_enabled(
            adversarial_review=StageConfig(params={"enabled": True}),
            paper_synthesis=StageConfig(params={"enabled": True}),
            citation_audit=StageConfig(),
        ),
        max_total_time=1800.0,
        description=(
            "Full pipeline: literature search, ingestion, gap analysis, "
            "idea generation with tree search, novelty checking, feasibility "
            "scoring, metrics, proposal synthesis, adversarial review, "
            "paper synthesis, citation audit, proposal deepening, and export. "
            "~25 minutes."
        ),
    ))

    # ── FAST SCAN ─────────────────────────────────────────
    # Skips expensive stages: idea_generation (tree search),
    # novelty_checking, mechanical_metrics, adversarial_review,
    # paper_synthesis, and citation_audit.
    registry.register(StrategyConfig(
        name=PipelineStrategy.FAST_SCAN,
        stages=_all_stages_enabled(
            idea_generation=StageConfig(enabled=False),
            novelty_checking=StageConfig(enabled=False),
            mechanical_metrics=StageConfig(enabled=False),
            adversarial_review=StageConfig(enabled=False, params={"enabled": False}),
            paper_synthesis=StageConfig(enabled=False, params={"enabled": False}),
            citation_audit=StageConfig(enabled=False),
        ),
        max_total_time=300.0,
        description=(
            "Quick scan: literature search, ingestion, gap analysis, "
            "feasibility scoring, light synthesis, and export. "
            "Skips tree search, novelty checking, metrics, adversarial review, "
            "paper synthesis, and citation audit. ~2-5 minutes."
        ),
    ))

    # ── ACADEMIC PROPOSAL ─────────────────────────────────
    # Like deep_research but with longer timeouts and stricter scoring.
    # Paper synthesis enabled for publication-ready output.
    # Citation audit ON.
    registry.register(StrategyConfig(
        name=PipelineStrategy.ACADEMIC_PROPOSAL,
        stages=_all_stages_enabled(
            novelty_checking=StageConfig(timeout=600.0, params={"threshold": 0.7}),
            feasibility_scoring=StageConfig(timeout=600.0, params={"threshold": 0.7}),
            proposal_synthesis=StageConfig(timeout=900.0),
            adversarial_review=StageConfig(timeout=600.0, params={"enabled": True}),
            paper_synthesis=StageConfig(timeout=900.0, params={"enabled": True}),
            citation_audit=StageConfig(),
        ),
        max_total_time=3600.0,
        description=(
            "Academic-grade proposal: full pipeline with longer timeouts, "
            "stricter novelty/feasibility thresholds, paper synthesis "
            "and citation audit for publication-ready output. ~45 minutes."
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
            paper_synthesis=StageConfig(enabled=False, params={"enabled": False}),
            citation_audit=StageConfig(enabled=False),
            proposal_deepening=StageConfig(enabled=False),
        ),
        max_total_time=600.0,
        description=(
            "Literature review only: search, ingest, analyze gaps, then export. "
            "No idea generation, proposal synthesis, or citation audit. ~10 minutes."
        ),
    ))
