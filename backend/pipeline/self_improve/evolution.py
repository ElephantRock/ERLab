"""Pipeline parameter evolution using gepa-inspired evolutionary optimization."""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.pipeline.self_improve.constraints import ConstraintConfig, ConstraintValidator
from backend.pipeline.self_improve.fitness import FitnessScore
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

    def __init__(
        self,
        frontier: ParetoFrontier,
        constraint_config: ConstraintConfig | None = None,
        git_dir: str | None = None,
    ):
        self._frontier = frontier
        self._constraints = ConstraintValidator(constraint_config) if constraint_config else None
        self._git_dir = git_dir  # None = no git tracking

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
                if isinstance(val, int | float):
                    params[key] = type(val)(max(lo, min(hi, val)))

        return params

    def snapshot(self, params: dict, run_id: str) -> str | None:
        """Commit params to git (autonovel pattern). Returns commit hash or None."""
        if not self._git_dir:
            return None
        path = Path(self._git_dir) / "evolved_params.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(params, indent=2, sort_keys=True))
        subprocess.run(["git", "add", str(path)], cwd=self._git_dir, capture_output=True)
        r = subprocess.run(
            ["git", "commit", "-m", f"evolve: {run_id}", "--allow-empty"],
            cwd=self._git_dir,
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            h = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self._git_dir,
                capture_output=True,
                text=True,
            )
            logger.info("Git snapshot: %s for run %s", h.stdout.strip(), run_id)
            return h.stdout.strip()
        return None

    def undo(self) -> dict | None:
        """Revert last parameter commit. Returns previous params or None."""
        if not self._git_dir:
            return None
        r = subprocess.run(
            ["git", "reset", "--hard", "HEAD~1"], cwd=self._git_dir, capture_output=True, text=True
        )
        if r.returncode == 0:
            path = Path(self._git_dir) / "evolved_params.json"
            if path.exists():
                return json.loads(path.read_text())
        return None

    def evaluate(
        self,
        params: dict,
        run_id: str,
        avg_idea_score: float,
        avg_novelty_score: float = 0.0,
        idea_diversity: float = 0.0,
        total_tokens: int = 0,
        good_ideas: int = 0,
        fitness: FitnessScore | None = None,
    ) -> FrontierPoint | None:
        """Record the outcome of a run as a frontier point.

        Returns None if constraint validation fails (artifact rejected).
        """
        # Constraint gate: reject evolved params that violate hard limits
        if self._constraints:
            params_str = json.dumps(params, sort_keys=True)
            baseline_str = json.dumps(self.propose(), sort_keys=True)
            if not self._constraints.all_passed(params_str, baseline_str):
                logger.warning("Evolved params rejected by constraint gate for run %s", run_id)
                return None

        efficiency = good_ideas / max(1, total_tokens) * 10000  # Good ideas per 10K tokens

        scores = {
            FrontierType.QUALITY.value: avg_idea_score,
            FrontierType.NOVELTY.value: avg_novelty_score,
            FrontierType.DIVERSITY.value: idea_diversity,
            FrontierType.EFFICIENCY.value: efficiency,
        }

        # Multi-dimensional fitness scoring (hermes-agent-self-evolution pattern)
        if fitness is not None:
            scores[FrontierType.FITNESS.value] = fitness.composite

        point = FrontierPoint(
            params=params,
            scores=scores,
            run_id=run_id,
            timestamp=datetime.now(),
        )

        is_non_dominated = self._frontier.add(point)
        if is_non_dominated:
            logger.info(
                "New Pareto-optimal point: quality=%.3f novelty=%.3f",
                avg_idea_score,
                avg_novelty_score,
            )

        # Git snapshot for rollback (autonovel pattern)
        self.snapshot(params, run_id)

        return point

    def apply_lessons(self, lessons: list[str], params: dict[str, Any]) -> dict[str, Any]:
        """Feed extracted lessons back into parameter proposals.

        Analyzes lesson categories and nudges evolved params accordingly.
        """
        adjusted = dict(params)
        for lesson in lessons:
            lesson_lower = lesson.lower()
            if "temperature" in lesson_lower or "too conservative" in lesson_lower:
                for key in ("ideator_temperature", "critic_temperature", "refiner_temperature"):
                    if key in adjusted:
                        adjusted[key] = min(
                            PARAM_RANGES[key][1],
                            adjusted[key] + 0.05,
                        )
            elif "too many ideas" in lesson_lower or "reduce ideas" in lesson_lower:
                if "ideas_per_round" in adjusted:
                    adjusted["ideas_per_round"] = max(
                        PARAM_RANGES["ideas_per_round"][0],
                        int(adjusted["ideas_per_round"]) - 1,
                    )
            elif "too few" in lesson_lower or "increase gaps" in lesson_lower:
                if "max_gaps" in adjusted:
                    adjusted["max_gaps"] = min(
                        PARAM_RANGES["max_gaps"][1],
                        int(adjusted["max_gaps"]) + 1,
                    )
        return adjusted
