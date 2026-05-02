"""World model change detection — structured diffs from KnowledgeGraph versioning.

Monitors changes recorded by the KG's VersionLog and produces structured
summaries with severity classification. Triggers goal re-evaluation
when significant changes are detected.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.pipeline.autonomy.goals import GoalManager
    from backend.pipeline.knowledge.graph import KnowledgeGraph

logger = logging.getLogger(__name__)


class ChangeSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class EntityChange:
    entity_id: str
    operation: str  # "add", "truth_update", "reinforce", "weaken", "merge"
    field: str = ""
    old_value: Any = None
    new_value: Any = None


@dataclass
class ChangeSummary:
    """Structured summary of changes between two KG versions."""

    from_version: int
    to_version: int
    entity_changes: list[EntityChange] = field(default_factory=list)
    relationship_changes: list[dict[str, Any]] = field(default_factory=list)
    severity: ChangeSeverity = ChangeSeverity.LOW
    total_changes: int = 0


class WorldModelChangeDetector:
    """Detects and summarizes changes in the KnowledgeGraph.

    Wraps the KG's VersionLog to produce structured change summaries
    with severity classification.
    """

    def __init__(self, kg: KnowledgeGraph, contradiction_scanner=None):
        self._kg = kg
        self._contradiction_scanner = contradiction_scanner

    def detect_changes(self, since_version: int = 0) -> ChangeSummary:
        """Produce a structured summary of all changes since a version."""
        if not hasattr(self._kg, "_version_log") or self._kg._version_log is None:
            return ChangeSummary(from_version=since_version, to_version=since_version)

        changes = self._kg._version_log.get_changes_since(since_version)
        if not changes:
            current = self._kg._version_log.get_version()
            return ChangeSummary(from_version=since_version, to_version=current)

        entity_changes: list[EntityChange] = []
        relationship_changes: list[dict[str, Any]] = []

        for change in changes:
            if change.operation in ("entity_add", "truth_update", "reinforce", "weaken", "merge"):
                entity_changes.append(EntityChange(
                    entity_id=change.target_id,
                    operation=change.operation,
                    field="truth" if change.operation == "truth_update" else "existence",
                    old_value=change.delta.get("old_truth") if change.delta else None,
                    new_value=change.delta.get("new_truth") if change.delta else None,
                ))
            elif change.operation in ("relationship_add",):
                relationship_changes.append({
                    "target_id": change.target_id,
                    "operation": change.operation,
                    "delta": change.delta,
                })

        summary = ChangeSummary(
            from_version=since_version,
            to_version=changes[-1].version if changes else since_version,
            entity_changes=entity_changes,
            relationship_changes=relationship_changes,
            total_changes=len(changes),
        )
        summary.severity = self.classify_severity(summary)
        return summary

    @staticmethod
    def classify_severity(summary: ChangeSummary) -> ChangeSeverity:
        """Classify the overall severity of a change summary."""
        high = 0
        medium = 0

        for ec in summary.entity_changes:
            if ec.operation == "weaken":
                # Check for significant truth drops
                if ec.old_value is not None and ec.new_value is not None:
                    try:
                        drop = float(ec.old_value) - float(ec.new_value)
                        if drop > 0.3:
                            high += 1
                        elif drop > 0.1:
                            medium += 1
                    except (TypeError, ValueError):
                        medium += 1
                else:
                    medium += 1
            elif ec.operation == "merge":
                high += 1
            elif ec.operation == "entity_add":
                pass  # New entities are low severity

        if high > 0:
            return ChangeSeverity.HIGH
        if medium >= 2:
            return ChangeSeverity.MEDIUM
        return ChangeSeverity.LOW

    async def check_and_notify(
        self,
        goal_manager: GoalManager | None = None,
        kg: KnowledgeGraph | None = None,
    ) -> ChangeSummary | None:
        """Check for changes and trigger goal re-evaluation if needed."""
        target_kg = kg or self._kg
        if not hasattr(target_kg, "_version_log") or target_kg._version_log is None:
            return None

        current_version = target_kg._version_log.latest_version
        if current_version == 0:
            return None

        summary = self.detect_changes(max(0, current_version - 50))

        if summary.severity == ChangeSeverity.HIGH and goal_manager:
            logger.info(
                "High-severity changes detected (%d changes), triggering goal re-evaluation",
                summary.total_changes,
            )
            try:
                reports = goal_manager.check_goal_conflicts(target_kg)
                if reports:
                    goal_manager.retract_conflicted_goals(reports)
                    logger.info("Retracted %d conflicted goals after change detection", len(reports))
            except Exception as e:
                logger.warning("Goal re-evaluation after change detection failed: %s", e)

        # Trigger contradiction scan on HIGH-severity changes
        if summary.severity == ChangeSeverity.HIGH and self._contradiction_scanner:
            try:
                contradiction_reports = await self._contradiction_scanner.scan()
                if contradiction_reports:
                    logger.warning(
                        "Contradiction scan after HIGH-severity change: %d contradictions found",
                        len(contradiction_reports),
                    )
            except Exception as e:
                logger.warning("Contradiction scan after change detection failed: %s", e)

        return summary
