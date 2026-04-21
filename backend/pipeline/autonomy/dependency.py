"""Goal Dependency Sets — Soar GDS-inspired conflict detection.

Tracks which world-model facts each goal depends on and flags goals
as conflicted when their supporting conditions change (entity removed,
truth dropped, relationship weakened).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GoalDependency(BaseModel):
    """A single dependency between a goal and a world-model fact."""

    goal_id: str
    depends_on_type: str  # entity_truth, entity_existence, relationship_weight, gap_confidence
    depends_on_id: str
    condition_description: str = ""
    recorded_at: datetime = Field(default_factory=datetime.now)


class ConflictReport(BaseModel):
    """Result of evaluating a goal's dependencies against current state."""

    goal_id: str
    goal_title: str = ""
    conflicts: list[GoalDependency] = Field(default_factory=list)
    severity: str = "none"  # none, low, medium, high
    recommended_action: str = "continue"  # continue, re-evaluate, retract, escalate


class GoalDependencyTracker:
    """Manages Goal Dependency Sets (Soar GDS pattern).

    Each goal has a set of dependencies on world-model facts. When
    those facts change, the tracker evaluates whether the goal is
    still viable.
    """

    def __init__(self):
        self._dependencies: dict[str, list[GoalDependency]] = {}

    def register_dependency(self, goal_id: str, dep: GoalDependency) -> None:
        self._dependencies.setdefault(goal_id, []).append(dep)

    def register_dependencies(self, goal_id: str, deps: list[GoalDependency]) -> None:
        self._dependencies.setdefault(goal_id, []).extend(deps)

    def get_dependencies(self, goal_id: str) -> list[GoalDependency]:
        return list(self._dependencies.get(goal_id, []))

    def remove_goal(self, goal_id: str) -> None:
        self._dependencies.pop(goal_id, None)

    def get_goals_affected_by(self, entity_id: str) -> list[str]:
        affected = []
        for goal_id, deps in self._dependencies.items():
            if any(d.depends_on_id == entity_id for d in deps):
                affected.append(goal_id)
        return affected

    def evaluate_conflicts(self, goal_id: str, kg) -> list[GoalDependency]:
        """Check dependencies against current graph state. Returns violated deps."""
        deps = self._dependencies.get(goal_id, [])
        if not deps:
            return []

        conflicts = []
        for dep in deps:
            if dep.depends_on_type == "entity_existence":
                entity = kg.get_entity(dep.depends_on_id)
                if entity is None:
                    conflicts.append(dep)
            elif dep.depends_on_type == "entity_truth":
                entity = kg.get_entity(dep.depends_on_id)
                if entity is None or entity.truth.expectation < 0.1:
                    conflicts.append(dep)
            elif dep.depends_on_type == "gap_confidence":
                # Gap confidence is checked against a threshold encoded in description
                pass  # Evaluated externally via check_goal_conflicts
        return conflicts

    def evaluate_all_conflicts(self, kg) -> dict[str, list[GoalDependency]]:
        result = {}
        for goal_id in self._dependencies:
            conflicts = self.evaluate_conflicts(goal_id, kg)
            if conflicts:
                result[goal_id] = conflicts
        return result

    @staticmethod
    def build_report(
        goal_id: str,
        goal_title: str,
        conflicts: list[GoalDependency],
    ) -> ConflictReport:
        """Build a ConflictReport with computed severity and recommended action."""
        if not conflicts:
            return ConflictReport(goal_id=goal_id, goal_title=goal_title)

        has_existence = any(c.depends_on_type == "entity_existence" for c in conflicts)
        has_truth = any(c.depends_on_type == "entity_truth" for c in conflicts)

        if has_existence:
            return ConflictReport(
                goal_id=goal_id,
                goal_title=goal_title,
                conflicts=conflicts,
                severity="high",
                recommended_action="retract",
            )
        if has_truth:
            return ConflictReport(
                goal_id=goal_id,
                goal_title=goal_title,
                conflicts=conflicts,
                severity="medium",
                recommended_action="re-evaluate",
            )
        return ConflictReport(
            goal_id=goal_id,
            goal_title=goal_title,
            conflicts=conflicts,
            severity="low",
            recommended_action="re-evaluate",
        )

    @property
    def goal_count(self) -> int:
        return len(self._dependencies)

    @property
    def total_dependencies(self) -> int:
        return sum(len(deps) for deps in self._dependencies.values())
