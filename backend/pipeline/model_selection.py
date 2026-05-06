"""Model selection: maps pipeline task types to appropriate providers.

Thinking tasks (classification, extraction, ranking) use a fast, cheap model.
Generation tasks (writing, synthesis, critique) use a powerful model.
When no model split is configured, both resolve to the default provider.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Task type classifications
THINKING_TASKS = frozenset({
    "classify", "extract", "rank", "filter", "dedup",
    "embedding", "cluster", "score", "evaluate",
})

GENERATION_TASKS = frozenset({
    "generate", "synthesize", "write", "critique",
    "ideate", "refine", "propose", "summarize",
})


class ModelSelector:
    """Maps task types to the appropriate LLM provider.

    Uses the thinking/generation model split when configured,
    falls back to the default provider otherwise.
    """

    def __init__(self, settings: Any = None) -> None:
        self._settings = settings
        self._thinking_provider = None
        self._generation_provider = None

    def resolve(self, task_type: str) -> Any:
        """Resolve the appropriate provider for a task type.

        Args:
            task_type: One of the task types in THINKING_TASKS or GENERATION_TASKS.
                       Unknown types default to the generation provider.

        Returns:
            LLM provider instance.
        """
        if task_type in THINKING_TASKS:
            return self._get_thinking()
        # Default: generation provider for all generation tasks and unknowns
        return self._get_generation()

    def _get_thinking(self) -> Any:
        if self._thinking_provider is None:
            from backend.providers.provider_factory import get_thinking_provider
            self._thinking_provider = get_thinking_provider(self._settings)
            logger.debug("Resolved thinking provider: %s", type(self._thinking_provider).__name__)
        return self._thinking_provider

    def _get_generation(self) -> Any:
        if self._generation_provider is None:
            from backend.providers.provider_factory import get_generation_provider
            self._generation_provider = get_generation_provider(self._settings)
            logger.debug("Resolved generation provider: %s", type(self._generation_provider).__name__)
        return self._generation_provider

    @staticmethod
    def is_thinking_task(task_type: str) -> bool:
        """Check if a task type is classified as a thinking task."""
        return task_type in THINKING_TASKS

    @staticmethod
    def is_generation_task(task_type: str) -> bool:
        """Check if a task type is classified as a generation task."""
        return task_type in GENERATION_TASKS
