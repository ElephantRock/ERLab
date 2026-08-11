"""3-tier context manager for LLM calls.

Manages token budgets across three tiers:
1. SYSTEM: Always included (SOUL.md, role definition)
2. DOMAIN: Papers, gaps, and domain knowledge
3. TASK: Current stage-specific instructions

Truncation priority: TASK truncated first, then DOMAIN.
SYSTEM is never truncated (HB-02).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Rough token estimate: ~4 chars per token for English text
CHARS_PER_TOKEN = 4


class ContextTier(str, Enum):
    SYSTEM = "system"
    DOMAIN = "domain"
    TASK = "task"


@dataclass
class ContextBudget:
    """Token budget configuration."""
    max_total_tokens: int = 8192
    system_reserve: int = 1024  # Minimum tokens reserved for system
    task_reserve: int = 512    # Minimum tokens reserved for task


class ContextManager:
    """Manages LLM context with token budgets.

    Three tiers of context:
    - SYSTEM: Role + SOUL.md philosophy (never truncated)
    - DOMAIN: Papers, gaps, domain knowledge (truncated if needed)
    - TASK: Current stage instructions (truncated first)
    """

    def __init__(self, budget: ContextBudget | None = None) -> None:
        self._budget = budget or ContextBudget()
        self._system_context: str = ""
        self._domain_contexts: list[str] = []
        self._task_context: str = ""

    def set_system(self, text: str) -> None:
        """Set the system context (never truncated)."""
        self._system_context = text

    def add_domain(self, text: str) -> None:
        """Add domain context (papers, gaps, etc.)."""
        self._domain_contexts.append(text)

    def set_task(self, text: str) -> None:
        """Set the task context (current stage instructions)."""
        self._task_context = text

    def build(self) -> str:
        """Build the complete context within token budget.

        Priority: SYSTEM (always) → TASK (if room) → DOMAIN (fills remaining).
        Truncation: DOMAIN items truncated first, then TASK.
        """
        # Start with system (HB-02: never truncated)
        system = self._system_context
        system_tokens = self._estimate_tokens(system)

        if system_tokens > self._budget.system_reserve:
            logger.warning(
                "System context (%d tokens) exceeds reserve (%d)",
                system_tokens, self._budget.system_reserve,
            )

        remaining = self._budget.max_total_tokens - system_tokens

        # Add task context (up to task_reserve)
        task = self._task_context
        task_tokens = self._estimate_tokens(task)
        task_budget = min(task_tokens, self._budget.task_reserve, remaining)
        if task_tokens > task_budget:
            task = self._truncate(task, task_budget)
        remaining -= self._estimate_tokens(task)

        # Add domain contexts (fills remaining)
        domain_parts: list[str] = []
        for dc in self._domain_contexts:
            dc_tokens = self._estimate_tokens(dc)
            if dc_tokens <= remaining:
                domain_parts.append(dc)
                remaining -= dc_tokens
            elif remaining > 100:
                # Truncate this domain context to fit
                domain_parts.append(self._truncate(dc, remaining))
                remaining = 0
            else:
                break

        # Assemble
        parts = []
        if system:
            parts.append(system)
        if domain_parts:
            parts.append("\n\n".join(domain_parts))
        if task:
            parts.append(task)

        result = "\n\n---\n\n".join(parts)
        total = self._estimate_tokens(result)

        if total > self._budget.max_total_tokens:
            logger.warning(
                "Context overflow: %d tokens (budget: %d)",
                total, self._budget.max_total_tokens,
            )

        return result

    @property
    def budget(self) -> ContextBudget:
        return self._budget

    @property
    def domain_count(self) -> int:
        return len(self._domain_contexts)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate."""
        return max(1, len(text) // CHARS_PER_TOKEN)

    @staticmethod
    def _truncate(text: str, max_tokens: int) -> str:
        """Truncate text to fit within token budget."""
        max_chars = max_tokens * CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text
        truncated = text[:max_chars]
        # Try to end at a sentence boundary
        last_period = truncated.rfind(".")
        if last_period > max_chars // 2:
            truncated = truncated[:last_period + 1]
        return truncated + "\n\n[... truncated ...]"
