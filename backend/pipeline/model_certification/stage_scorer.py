"""Base scorer contract and scorer registry.

All stage-specific scorers implement the StageScorer interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.pipeline.model_certification.eval_case import GoldAnswer, StageEvalCase


class StageScorer(ABC):
    """Base contract for stage-specific scoring."""

    stage: str = ""

    @abstractmethod
    def score(
        self,
        raw_output: str,
        parsed_output: dict | None,
        case: StageEvalCase,
        gold: GoldAnswer | None = None,
    ) -> dict[str, float]:
        """Score a model's output for a stage eval case.

        Returns:
            Dict of metric_name → score (0.0–1.0).
        """

    @abstractmethod
    def failures(
        self,
        raw_output: str,
        parsed_output: dict | None,
        case: StageEvalCase,
        gold: GoldAnswer | None = None,
    ) -> list[str]:
        """Return list of specific failure descriptions."""


class ScorerRegistry:
    """Maps stage names to scorer instances."""

    def __init__(self) -> None:
        self._scorers: dict[str, StageScorer] = {}

    def register(self, scorer: StageScorer) -> None:
        """Register a scorer for its stage."""
        self._scorers[scorer.stage] = scorer

    def get(self, stage: str) -> StageScorer | None:
        """Get the scorer for a stage, or None."""
        return self._scorers.get(stage)

    def score(
        self,
        stage: str,
        raw_output: str,
        parsed_output: dict | None,
        case: StageEvalCase,
        gold: GoldAnswer | None = None,
    ) -> dict[str, float]:
        """Score using the stage-specific scorer. Returns empty dict if no scorer."""
        scorer = self.get(stage)
        if scorer is None:
            return {}
        return scorer.score(raw_output, parsed_output, case, gold)

    def failures(
        self,
        stage: str,
        raw_output: str,
        parsed_output: dict | None,
        case: StageEvalCase,
        gold: GoldAnswer | None = None,
    ) -> list[str]:
        """Get failures from the stage-specific scorer."""
        scorer = self.get(stage)
        if scorer is None:
            return []
        return scorer.failures(raw_output, parsed_output, case, gold)

    @property
    def stages(self) -> list[str]:
        """List registered stages."""
        return sorted(self._scorers.keys())


def create_default_registry() -> ScorerRegistry:
    """Create a registry with all built-in scorers registered."""
    from backend.pipeline.model_certification.scorers.adversarial_review import (
        AdversarialReviewScorer,
    )
    from backend.pipeline.model_certification.scorers.evidence_table import EvidenceTableScorer
    from backend.pipeline.model_certification.scorers.literature_filtering import (
        LiteratureFilteringScorer,
    )
    from backend.pipeline.model_certification.scorers.paper_extraction import PaperExtractionScorer
    from backend.pipeline.model_certification.scorers.query_generation import QueryGenerationScorer
    from backend.pipeline.model_certification.scorers.repair import RepairScorer
    from backend.pipeline.model_certification.scorers.synthesis import SynthesisScorer

    registry = ScorerRegistry()
    registry.register(QueryGenerationScorer())
    registry.register(LiteratureFilteringScorer())
    registry.register(PaperExtractionScorer())
    registry.register(EvidenceTableScorer())
    registry.register(SynthesisScorer())
    registry.register(RepairScorer())
    registry.register(AdversarialReviewScorer())
    return registry
