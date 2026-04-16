"""Goal management for research pipeline.

PUMA-inspired goal formation and scheduling: convert gaps to goals,
prioritize by impact/feasibility, decompose into sub-goals, and
track progress across runs.
"""

import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GoalStatus(str, Enum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class ResearchGoal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    source_gap_id: str | None = None
    description: str = ""
    priority: float = 0.5  # 0-1, computed from gap confidence * feasibility * impact
    status: GoalStatus = GoalStatus.PROPOSED
    sub_goals: list[str] = []      # IDs of child goals
    parent_goal_id: str | None = None
    progress: float = 0.0          # 0-1
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()


class GoalManager:
    """PUMA-inspired goal formation and scheduling."""

    def __init__(self, persist_path: str = "./data/goals.json"):
        self._path = Path(persist_path)
        self._goals: dict[str, ResearchGoal] = {}
        self._load()

    def create_from_gaps(self, gaps: list) -> list[ResearchGoal]:
        """Convert research gaps into actionable goals."""
        new_goals = []
        for gap in gaps:
            goal = ResearchGoal(
                title=f"Investigate: {gap.title}",
                description=gap.description,
                priority=gap.confidence,
                status=GoalStatus.PROPOSED,
            )
            self._goals[goal.id] = goal
            new_goals.append(goal)

        if new_goals:
            self._save()
        return new_goals

    def decompose(self, goal: ResearchGoal, sub_descriptions: list[str] | None = None) -> list[ResearchGoal]:
        """Decompose a goal into sub-goals."""
        if sub_descriptions is None:
            sub_descriptions = [
                f"Literature search for {goal.title}",
                f"Generate ideas for {goal.title}",
                f"Evaluate feasibility of {goal.title}",
            ]

        sub_goals = []
        for desc in sub_descriptions:
            sub = ResearchGoal(
                title=desc,
                parent_goal_id=goal.id,
                priority=goal.priority * 0.8,
                status=GoalStatus.PROPOSED,
            )
            goal.sub_goals.append(sub.id)
            self._goals[sub.id] = sub
            sub_goals.append(sub)

        self._save()
        return sub_goals

    def prioritize(self, goals: list[ResearchGoal] | None = None) -> list[ResearchGoal]:
        """Return goals sorted by priority (highest first)."""
        if goals is None:
            goals = list(self._goals.values())
        return sorted(goals, key=lambda g: g.priority, reverse=True)

    def update_progress(self, goal_id: str, progress: float) -> None:
        """Update goal progress."""
        if goal_id in self._goals:
            goal = self._goals[goal_id]
            goal.progress = min(1.0, max(0.0, progress))
            goal.updated_at = datetime.now()
            if goal.progress >= 1.0:
                goal.status = GoalStatus.COMPLETED
            self._save()

    def get_active_goals(self) -> list[ResearchGoal]:
        """Get all active (non-completed, non-abandoned) goals."""
        return [
            g for g in self._goals.values()
            if g.status in (GoalStatus.PROPOSED, GoalStatus.ACTIVE, GoalStatus.IN_PROGRESS)
        ]

    def get_next_goal(self) -> ResearchGoal | None:
        """Get the highest-priority active goal."""
        active = self.get_active_goals()
        if not active:
            return None
        return self.prioritize(active)[0]

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            for gd in data.get("goals", []):
                goal = ResearchGoal(**gd)
                self._goals[goal.id] = goal
        except Exception as e:
            logger.warning("Failed to load goals: %s", e)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({
            "goals": [g.model_dump(mode="json") for g in self._goals.values()],
        }, indent=2, default=str))
