"""Pareto-efficient frontier tracking for pipeline parameter optimization.

Tracks non-dominated points across 4 objectives (quality, novelty,
diversity, efficiency) and provides parameter suggestion via semantic
crossover (gepa pattern).
"""

import json
import random
from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel


class FrontierType(str, Enum):
    QUALITY = "quality"          # Maximize average idea score
    NOVELTY = "novelty"          # Maximize average novelty score
    DIVERSITY = "diversity"      # Maximize idea diversity
    EFFICIENCY = "efficiency"    # Minimize tokens per good idea


class FrontierPoint(BaseModel):
    params: dict[str, float | int | str]
    scores: dict[str, float]
    run_id: str = ""
    timestamp: datetime = datetime.now()


class ParetoFrontier:
    """Track Pareto-efficient frontier across pipeline runs."""

    def __init__(self, persist_path: str = "./data/self_improve/frontier.json"):
        self._path = Path(persist_path)
        self._points: list[FrontierPoint] = []
        self._load()

    def add(self, point: FrontierPoint) -> bool:
        """Add a point. Returns True if non-dominated (Pareto-optimal)."""
        # Remove existing points dominated by the new one
        new_dominated = []
        for existing in self._points:
            if self._dominates(point, existing):
                new_dominated.append(existing)

        # Check if new point is dominated by any existing
        for existing in self._points:
            if self._dominates(existing, point):
                self._points.append(point)
                self._save()
                return False

        # New point is non-dominated — remove dominated points
        for d in new_dominated:
            self._points.remove(d)
        self._points.append(point)
        self._save()
        return True

    def get_best(self, objective: FrontierType) -> FrontierPoint | None:
        """Get the best point for a specific objective."""
        if not self._points:
            return None
        return max(self._points, key=lambda p: p.scores.get(objective.value, 0.0))

    def suggest_params(self) -> dict[str, float | int | str]:
        """Suggest parameters via semantic crossover between two Pareto-optimal parents."""
        if len(self._points) < 2:
            return self._points[0].params if self._points else {}

        # Pick two random non-dominated points as parents
        parents = random.sample(self._points, min(2, len(self._points)))

        # Semantic crossover: for each param, pick from parent A or parent B
        child = {}
        all_keys = set(parents[0].params.keys()) | set(parents[1].params.keys())
        for key in all_keys:
            if key in parents[0].params and key in parents[1].params:
                val_a = parents[0].params[key]
                val_b = parents[1].params[key]
                if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                    # Numeric: weighted average with random weight
                    w = random.random()
                    child[key] = type(val_a)(w * val_a + (1 - w) * val_b)
                else:
                    # Categorical: random selection
                    child[key] = random.choice([val_a, val_b])
            else:
                child[key] = parents[0].params.get(key, parents[1].params.get(key))

        return child

    @property
    def frontier_size(self) -> int:
        return len(self._points)

    @staticmethod
    def _dominates(a: FrontierPoint, b: FrontierPoint) -> bool:
        """Check if point A dominates point B (A >= B on all objectives, A > B on at least one)."""
        all_objectives = set(a.scores.keys()) | set(b.scores.keys())
        if not all_objectives:
            return False

        at_least_one_better = False
        for obj in all_objectives:
            score_a = a.scores.get(obj, 0.0)
            score_b = b.scores.get(obj, 0.0)
            if score_a < score_b:
                return False
            if score_a > score_b:
                at_least_one_better = True

        return at_least_one_better

    def _load(self) -> None:
        if self._path.exists():
            data = json.loads(self._path.read_text())
            self._points = [FrontierPoint(**p) for p in data.get("points", [])]

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({
            "points": [p.model_dump(mode="json") for p in self._points],
        }, indent=2, default=str))
