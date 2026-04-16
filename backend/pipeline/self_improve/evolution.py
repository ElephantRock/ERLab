"""Pipeline parameter evolution using gepa-inspired evolutionary optimization."""

import logging
from datetime import datetime

from backend.pipeline.self_improve.frontier import FrontierPoint, FrontierType, ParetoFrontier

logger = logging.getLogger(__name__)

# Default evolvable parameter ranges
PARAM_RANGES: dict[str, tuple[float, float]] = {
    "generation_rounds": (1, 5),
    "ideas_per_round": (2, 6),
    "ideator_temperature": (0.5, 1.2),
    "critic_temperature": (0.1, 0.5),
    "refiner_temperature": (0.3, 0.8),
    "max_gaps": (3, 10),
    "novelty_top_k": (10, 30),
}


class PipelineEvolver:
    """gepa-inspired evolutionary optimization for pipeline parameters."""

    def __init__(self, frontier: ParetoFrontier):
        self._frontier = frontier

    def propose(self) -> dict[str, float | int | str]:
        """Propose parameters for next run using Pareto frontier crossover."""
        params = self._frontier.suggest_params()
        if not params:
            # No history yet — return defaults
            return {
                "generation_rounds": 2,
                "ideas_per_round": 3,
                "ideator_temperature": 0.8,
                "critic_temperature": 0.3,
                "refiner_temperature": 0.5,
                "max_gaps": 5,
                "novelty_top_k": 20,
            }

        # Clamp values to valid ranges
        for key, (lo, hi) in PARAM_RANGES.items():
            if key in params:
                val = params[key]
                if isinstance(val, (int, float)):
                    params[key] = type(val)(max(lo, min(hi, val)))

        return params

    def evaluate(
        self,
        params: dict,
        run_id: str,
        avg_idea_score: float,
        avg_novelty_score: float = 0.0,
        idea_diversity: float = 0.0,
        total_tokens: int = 0,
        good_ideas: int = 0,
    ) -> FrontierPoint:
        """Record the outcome of a run as a frontier point."""
        efficiency = good_ideas / max(1, total_tokens) * 10000  # Good ideas per 10K tokens

        point = FrontierPoint(
            params=params,
            scores={
                FrontierType.QUALITY.value: avg_idea_score,
                FrontierType.NOVELTY.value: avg_novelty_score,
                FrontierType.DIVERSITY.value: idea_diversity,
                FrontierType.EFFICIENCY.value: efficiency,
            },
            run_id=run_id,
            timestamp=datetime.now(),
        )

        is_non_dominated = self._frontier.add(point)
        if is_non_dominated:
            logger.info("New Pareto-optimal point: quality=%.3f novelty=%.3f", avg_idea_score, avg_novelty_score)

        return point
