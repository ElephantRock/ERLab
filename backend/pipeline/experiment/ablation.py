"""Ablation Study Runner — runs pipeline variants for component comparison.

BATCH-RAG-08: Runs the pipeline multiple times, each time disabling one
component, to measure the impact of each component on overall quality.

Uses existing StageConfig(enabled=False) pattern. Produces comparison
reports with metric deltas between variants.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.pipeline.strategies.models import PipelineStrategy, StageConfig, StrategyConfig

logger = logging.getLogger(__name__)

# Components that can be ablated
ABLATABLE_COMPONENTS = [
    "gap_reflection",
    "idea_reflection",
    "novelty_checking",
    "feasibility_scoring",
    "adversarial_review",
    "evaluation",
    "paper_synthesis",
    "citation_audit",
    "proposal_deepening",
]


@dataclass
class AblationVariant:
    """One variant of the ablation study."""

    name: str
    disabled_components: list[str] = field(default_factory=list)
    strategy: PipelineStrategy = PipelineStrategy.DEEP_RESEARCH

    def to_strategy_config(self) -> StrategyConfig:
        """Convert to StrategyConfig with specified components disabled."""
        from backend.pipeline.strategies.presets import _all_stages_enabled

        overrides = {
            comp: StageConfig(enabled=False, timeout=0.0)
            for comp in self.disabled_components
        }
        stages = _all_stages_enabled(**overrides)
        return StrategyConfig(
            name=self.strategy,
            stages=stages,
            max_total_time=1800.0,
            description=f"Ablation: disabled {', '.join(self.disabled_components)}",
        )


@dataclass
class AblationResult:
    """Result of running one ablation variant."""

    variant_name: str
    disabled_components: list[str]
    metrics: dict[str, float] = field(default_factory=dict)
    ideas_count: int = 0
    gaps_count: int = 0
    elapsed_seconds: float = 0.0
    error: str | None = None


@dataclass
class AblationReport:
    """Full ablation study report comparing all variants."""

    domain: str = ""
    baseline_metrics: dict[str, float] = field(default_factory=dict)
    variants: list[AblationResult] = field(default_factory=list)
    deltas: dict[str, dict[str, float]] = field(default_factory=dict)

    def compute_deltas(self) -> None:
        """Compute metric deltas relative to baseline."""
        self.deltas = {}
        for variant in self.variants:
            variant_deltas = {}
            for metric_name, baseline_value in self.baseline_metrics.items():
                variant_value = variant.metrics.get(metric_name, 0.0)
                variant_deltas[metric_name] = variant_value - baseline_value
            self.deltas[variant.variant_name] = variant_deltas

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "baseline_metrics": self.baseline_metrics,
            "variants": [
                {
                    "name": v.variant_name,
                    "disabled": v.disabled_components,
                    "metrics": v.metrics,
                    "ideas_count": v.ideas_count,
                    "gaps_count": v.gaps_count,
                    "elapsed_seconds": round(v.elapsed_seconds, 1),
                    "error": v.error,
                }
                for v in self.variants
            ],
            "deltas": self.deltas,
        }


class AblationRunner:
    """Runs ablation studies by disabling components one at a time.

    Parameters
    ----------
    dry_run:
        If True, generates the plan but doesn't execute pipelines.
    """

    def __init__(self, dry_run: bool = True) -> None:
        self._dry_run = dry_run

    def plan_ablation(
        self,
        domain: str,
        strategy: PipelineStrategy = PipelineStrategy.DEEP_RESEARCH,
        components: list[str] | None = None,
    ) -> list[AblationVariant]:
        """Plan ablation variants: baseline + one-disabled-per-variant.

        Returns a list of AblationVariant configs ready for execution.
        """
        if components is None:
            components = ABLATABLE_COMPONENTS

        variants = [
            # Baseline: all components enabled
            AblationVariant(
                name="baseline",
                disabled_components=[],
                strategy=strategy,
            )
        ]

        # One variant per component disabled
        for comp in components:
            variants.append(
                AblationVariant(
                    name=f"without_{comp}",
                    disabled_components=[comp],
                    strategy=strategy,
                )
            )

        logger.info(
            "Planned ablation study: %d variants (1 baseline + %d ablations)",
            len(variants),
            len(variants) - 1,
        )
        return variants

    async def run_ablation(
        self,
        domain: str,
        strategy: PipelineStrategy = PipelineStrategy.DEEP_RESEARCH,
        components: list[str] | None = None,
    ) -> AblationReport:
        """Run the full ablation study.

        In dry_run mode, returns a mock report for testing.
        """
        variants = self.plan_ablation(domain, strategy, components)
        report = AblationReport(domain=domain)

        for variant in variants:
            if self._dry_run:
                # Mock result
                result = AblationResult(
                    variant_name=variant.name,
                    disabled_components=variant.disabled_components,
                    metrics={
                        "hit_rate": 0.85 if not variant.disabled_components else 0.80,
                        "mrr": 0.72 if not variant.disabled_components else 0.65,
                        "ideas_count": 2,
                        "gaps_count": 5,
                    },
                )
            else:
                result = await self._execute_variant(variant, domain)

            if variant.name == "baseline":
                report.baseline_metrics = result.metrics
            report.variants.append(result)

        report.compute_deltas()
        return report

    async def _execute_variant(
        self,
        variant: AblationVariant,
        domain: str,
    ) -> AblationResult:
        """Execute a single ablation variant (real pipeline run)."""
        try:
            from backend.config import get_settings
            from backend.pipeline.orchestrator import PipelineOrchestrator

            settings = get_settings()
            orchestrator = PipelineOrchestrator(settings=settings)

            config = variant.to_strategy_config()
            import time
            start = time.time()

            result = await orchestrator.run(
                domain=domain,
                strategy=variant.strategy.value,
                params=config.to_dict(),
            )

            elapsed = time.time() - start

            return AblationResult(
                variant_name=variant.name,
                disabled_components=variant.disabled_components,
                ideas_count=len(result.ideas) if result else 0,
                gaps_count=len(result.gaps) if result else 0,
                elapsed_seconds=elapsed,
            )
        except Exception as e:
            logger.error("Ablation variant %s failed: %s", variant.name, str(e)[:100])
            return AblationResult(
                variant_name=variant.name,
                disabled_components=variant.disabled_components,
                error=str(e)[:200],
            )
