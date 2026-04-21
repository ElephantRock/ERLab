"""Layered guardrail system for value alignment.

Three guardrail levels: INPUT (validate LLM inputs), OUTPUT (validate LLM
outputs), TOOL (validate tool call arguments). Each guardrail can be a
tripwire — a hard block that immediately halts execution.

Inspired by OpenAI Agents 3-level guardrails with tripwire semantics.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class GuardrailLevel(str, Enum):
    INPUT = "input"
    OUTPUT = "output"
    TOOL = "tool"


@dataclass
class GuardrailResult:
    """Result of a guardrail check."""
    passed: bool
    blocked_reason: str = ""
    tripwire: bool = False
    guardrail_name: str = ""

    @staticmethod
    def ok() -> GuardrailResult:
        return GuardrailResult(passed=True)

    @staticmethod
    def block(reason: str, *, tripwire: bool = False, name: str = "") -> GuardrailResult:
        return GuardrailResult(
            passed=False, blocked_reason=reason, tripwire=tripwire, guardrail_name=name
        )


class Guardrail(ABC):
    """Abstract guardrail — checks content and returns pass/fail."""

    name: str = ""
    level: GuardrailLevel = GuardrailLevel.INPUT

    @abstractmethod
    def check(self, content: str, context: dict | None = None) -> GuardrailResult:
        ...


class RegexGuardrail(Guardrail):
    """Pattern-based guardrail — fast, no LLM required."""

    def __init__(
        self,
        name: str,
        patterns: list[str],
        level: GuardrailLevel = GuardrailLevel.INPUT,
        tripwire: bool = False,
        block_message: str = "",
    ):
        self.name = name
        self.level = level
        self._patterns = [re.compile(p, re.IGNORECASE) for p in patterns]
        self._tripwire = tripwire
        self._block_message = block_message or f"Blocked by {name}"

    def check(self, content: str, context: dict | None = None) -> GuardrailResult:
        for pattern in self._patterns:
            if pattern.search(content):
                return GuardrailResult.block(
                    self._block_message,
                    tripwire=self._tripwire,
                    name=self.name,
                )
        return GuardrailResult.ok()


class LLMGuardrail(Guardrail):
    """LLM-based content guardrail — uses structured output for classification."""

    def __init__(
        self,
        name: str,
        provider: Any,
        prompt_template: str,
        level: GuardrailLevel = GuardrailLevel.OUTPUT,
        tripwire: bool = False,
    ):
        self.name = name
        self.level = level
        self._provider = provider
        self._prompt_template = prompt_template
        self._tripwire = tripwire

    async def check_async(self, content: str, context: dict | None = None) -> GuardrailResult:
        try:
            result = await self._provider.structured_output(
                messages=[{"role": "user", "content": self._prompt_template.format(content=content)}],
                schema={
                    "type": "object",
                    "properties": {
                        "is_violation": {"type": "boolean"},
                        "reason": {"type": "string"},
                    },
                    "required": ["is_violation"],
                },
                temperature=0.0,
            )
            if result.get("is_violation"):
                return GuardrailResult.block(
                    result.get("reason", f"Blocked by {self.name}"),
                    tripwire=self._tripwire,
                    name=self.name,
                )
            return GuardrailResult.ok()
        except Exception as e:
            logger.warning("LLM guardrail '%s' check failed: %s", self.name, e)
            return GuardrailResult.ok()  # Fail open — don't block on LLM errors

    def check(self, content: str, context: dict | None = None) -> GuardrailResult:
        # Synchronous fallback — returns pass. Use check_async() for real checks.
        return GuardrailResult.ok()


class TripwireGuardrail(Guardrail):
    """Wraps any guardrail and makes failures into tripwires (hard blocks)."""

    def __init__(self, wrapped: Guardrail):
        self.name = f"tripwire({wrapped.name})"
        self.level = wrapped.level
        self._wrapped = wrapped

    def check(self, content: str, context: dict | None = None) -> GuardrailResult:
        result = self._wrapped.check(content, context)
        if not result.passed:
            result.tripwire = True
        return result


class GuardrailStack:
    """Runs multiple guardrails in order. Short-circuits on tripwire."""

    def __init__(self, guardrails: list[Guardrail] | None = None):
        self._guardrails: list[Guardrail] = guardrails or []

    def add(self, guardrail: Guardrail) -> None:
        self._guardrails.append(guardrail)

    def check(self, content: str, context: dict | None = None) -> GuardrailResult:
        """Run all guardrails. Returns first failure or overall pass."""
        for g in self._guardrails:
            result = g.check(content, context)
            if not result.passed:
                logger.info(
                    "Guardrail '%s' blocked content: %s (tripwire=%s)",
                    g.name, result.blocked_reason, result.tripwire,
                )
                return result
        return GuardrailResult.ok()

    async def check_async(self, content: str, context: dict | None = None) -> GuardrailResult:
        """Run all guardrails, including async LLM guardrails."""
        for g in self._guardrails:
            if isinstance(g, LLMGuardrail):
                result = await g.check_async(content, context)
            else:
                result = g.check(content, context)
            if not result.passed:
                logger.info(
                    "Guardrail '%s' blocked content: %s (tripwire=%s)",
                    g.name, result.blocked_reason, result.tripwire,
                )
                return result
        return GuardrailResult.ok()

    def by_level(self, level: GuardrailLevel) -> GuardrailStack:
        """Return a sub-stack filtered by level."""
        return GuardrailStack([g for g in self._guardrails if g.level == level])


# ---- Built-in Guardrails ----

def harmful_content_input_guardrail() -> RegexGuardrail:
    """Basic harmful content patterns for input checking."""
    return RegexGuardrail(
        name="harmful_content_input",
        patterns=[
            r"\bhow\s+to\s+(make|build|create|synthesize)\s+(weapon|bomb|explosive|poison)",
            r"\bhow\s+to\s+hack\s+(into|a|the|someone)",
            r"\b exploiting\s+(children|minors)",
        ],
        level=GuardrailLevel.INPUT,
        tripwire=True,
        block_message="Query contains potentially harmful content",
    )


def pii_guardrail() -> RegexGuardrail:
    """Detect common PII patterns."""
    return RegexGuardrail(
        name="pii_detection",
        patterns=[
            r"\b\d{3}[-.]?\d{2}[-.]?\d{4}\b",  # SSN-like
            r"\b\d{16}\b",  # Credit card-like
        ],
        level=GuardrailLevel.INPUT,
        tripwire=False,
        block_message="Query may contain personally identifiable information",
    )


def citation_integrity_output_guardrail() -> RegexGuardrail:
    """Check outputs for unsupported claims."""
    return RegexGuardrail(
        name="citation_integrity_output",
        patterns=[],  # No regex patterns — this is a placeholder for LLM-based checking
        level=GuardrailLevel.OUTPUT,
        tripwire=False,
    )


def default_input_guardrails() -> GuardrailStack:
    return GuardrailStack([
        harmful_content_input_guardrail(),
        pii_guardrail(),
    ])
