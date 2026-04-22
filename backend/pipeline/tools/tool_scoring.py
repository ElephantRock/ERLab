"""Post-retrieval tool scoring — relevance, trust penalty, recency bonus."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from backend.pipeline.tools.tool_index import ToolSearchResult

if TYPE_CHECKING:
    from backend.pipeline.tools.registry import ToolDefinition

logger = logging.getLogger(__name__)


class ToolScore(BaseModel):
    tool_name: str
    relevance: float
    trust_penalty: float
    recency_bonus: float
    composite: float


class ToolScorer:
    """Scores tool search results with composite relevance/trust/recency."""

    def __init__(
        self,
        trust_penalty: float = 0.2,
        recency_weight: float = 0.1,
        relevance_weight: float = 0.7,
    ) -> None:
        self._trust_penalty = trust_penalty
        self._recency_weight = recency_weight
        self._relevance_weight = relevance_weight

    def score(
        self,
        results: list[ToolSearchResult],
        tools: dict[str, ToolDefinition],
        usage_history: dict[str, datetime] | None = None,
    ) -> list[ToolScore]:
        history = usage_history or {}
        now = datetime.now()
        scores: list[ToolScore] = []

        for r in results:
            tool = tools.get(r.tool_name)
            if not tool:
                continue

            relevance = r.score
            trust_pen = self._compute_trust_penalty(tool)
            recency = self._compute_recency_bonus(r.tool_name, history, now)

            composite = (
                self._relevance_weight * relevance
                + self._recency_weight * recency
                - trust_pen
            )

            scores.append(ToolScore(
                tool_name=r.tool_name,
                relevance=relevance,
                trust_penalty=trust_pen,
                recency_bonus=recency,
                composite=max(composite, 0.0),
            ))

        scores.sort(key=lambda s: s.composite, reverse=True)
        return scores

    def _compute_trust_penalty(self, tool: ToolDefinition) -> float:
        if tool.trust_level == "untrusted":
            return self._trust_penalty
        return 0.0

    def _compute_recency_bonus(
        self, tool_name: str, history: dict[str, datetime], now: datetime
    ) -> float:
        last_used = history.get(tool_name)
        if not last_used:
            return 0.0
        days_ago = (now - last_used).days
        return max(0.0, 1.0 - days_ago / 30.0)
