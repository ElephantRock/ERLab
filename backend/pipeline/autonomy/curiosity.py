"""Curiosity driver for autonomous exploration.

When idle too long, the curiosity driver suggests underexplored domains
for broad literature search. Inspired by PUMA's CuriosityDrive with
boredom mechanism.
"""

import logging

from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

EXPLORATION_PROMPT = """Based on the following research domains and topics already explored,
suggest a novel underexplored area that could yield high-impact research gaps.

Previously explored topics: {explored_topics}

Suggest a domain or subfield that:
1. Is adjacent to the explored topics
2. Has seen recent growth but is not yet saturated
3. Could benefit from cross-disciplinary approaches

Respond with JSON: {{"topic": "...", "rationale": "...", "search_queries": ["...", "..."]}}
"""


class CuriosityDriver:
    """Auto-trigger exploration when idle, based on novelty of unexplored domains."""

    def __init__(self, provider: LLMProvider):
        self._provider = provider
        self._explored_topics: list[str] = []

    def record_explored_topic(self, topic: str) -> None:
        """Record a topic that has been explored."""
        self._explored_topics.append(topic)

    async def suggest_exploration_topic(self) -> dict | None:
        """Identify an underexplored area and generate search queries."""
        if not self._explored_topics:
            return {
                "topic": "AI/NLP recent advances",
                "rationale": "Default starting point",
                "search_queries": ["AI/NLP recent advances 2024", "NLP open problems"],
            }

        topics_text = ", ".join(self._explored_topics[-10:])

        try:
            result = await self._provider.structured_output(
                messages=[
                    {"role": "system", "content": "You are a research exploration agent."},
                    {"role": "user", "content": EXPLORATION_PROMPT.format(explored_topics=topics_text)},
                ],
                schema={
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "rationale": {"type": "string"},
                        "search_queries": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["topic", "search_queries"],
                },
            )
            return result
        except Exception as e:
            logger.error("Curiosity exploration failed: %s", e)
            return None

    async def generate_search_queries(self, topic: str) -> list[str]:
        """Generate diverse search queries for a topic."""
        return [
            f"{topic} recent advances",
            f"{topic} open problems and challenges",
            f"{topic} survey 2024",
        ]
