"""Iterative reflection stage for pipeline quality improvement.

After gap analysis and ideation, the LLM evaluates its own output
and decides whether to retry with feedback. This produces higher-quality
gaps and ideas than single-pass generation.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass
class ReflectionResult:
    """Result of a single reflection evaluation."""

    score: float = 0.0
    passed: bool = False
    justification: str = ""
    feedback: str = ""
    iteration: int = 0

    def __post_init__(self):
        self.score = max(0.0, min(1.0, self.score))


class ReflectionStage:
    """Evaluates pipeline output quality and optionally triggers regeneration.

    Usage:
        reflector = ReflectionStage(provider=llm_provider, threshold=0.6, max_iterations=3)
        result = await reflector.reflect_with_retry(
            content=gaps,
            reflect_fn=reflector.reflect_gaps,
            regenerate_fn=regenerate_gaps,
        )
    """

    def __init__(
        self,
        provider: Any = None,
        threshold: float = 0.6,
        max_iterations: int = 3,
    ) -> None:
        self._provider = provider
        self._threshold = threshold
        self._max_iterations = max_iterations
        self._gap_prompt = self._load_prompt("gap_reflection.md")
        self._idea_prompt = self._load_prompt("idea_reflection.md")

    @staticmethod
    def _load_prompt(filename: str) -> str:
        path = _PROMPTS_DIR / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return "Evaluate the following research output. Score 0-1. Format: SCORE: N, PASSED: yes/no, JUSTIFICATION: ..., FEEDBACK: ..."

    async def reflect_gaps(
        self, gaps: list[Any], query: str = ""
    ) -> ReflectionResult:
        """Evaluate gap list quality."""
        if self._provider is None or not gaps:
            return ReflectionResult(score=1.0, passed=True, justification="No provider or no gaps — auto-pass")

        gap_descriptions = []
        for i, gap in enumerate(gaps[:10], 1):
            title = getattr(gap, "title", getattr(gap, "name", f"Gap {i}"))
            desc = getattr(gap, "description", "")
            gap_descriptions.append(f"{i}. {title}: {desc[:200]}")

        user_prompt = (
            f"Domain/Query: {query}\n\n"
            f"Research Gaps ({len(gaps)} total):\n"
            + "\n".join(gap_descriptions)
        )

        return await self._evaluate(self._gap_prompt, user_prompt)

    async def reflect_ideas(
        self, ideas: list[Any], gaps: list[Any] | None = None
    ) -> ReflectionResult:
        """Evaluate idea list quality."""
        if self._provider is None or not ideas:
            return ReflectionResult(score=1.0, passed=True, justification="No provider or no ideas — auto-pass")

        idea_descriptions = []
        for i, idea in enumerate(ideas[:10], 1):
            title = getattr(idea, "title", f"Idea {i}")
            desc = getattr(idea, "description", "")
            idea_descriptions.append(f"{i}. {title}: {desc[:200]}")

        user_prompt = f"Research Ideas ({len(ideas)} total):\n" + "\n".join(idea_descriptions)
        return await self._evaluate(self._idea_prompt, user_prompt)

    async def reflect_with_retry(
        self,
        content: Any,
        reflect_fn: Any,
        regenerate_fn: Any,
    ) -> tuple[Any, list[ReflectionResult]]:
        """Run reflection loop: evaluate, regenerate if needed, repeat.

        Args:
            content: The current output to evaluate (gaps or ideas).
            reflect_fn: Async function that evaluates content → ReflectionResult.
            regenerate_fn: Async function that takes (content, feedback) → new content.

        Returns:
            Tuple of (final_content, list of ReflectionResult per iteration).
        """
        results: list[ReflectionResult] = []
        current = content

        for iteration in range(1, self._max_iterations + 1):
            try:
                result = await reflect_fn(current)
            except Exception as e:
                logger.warning("Reflection failed (iteration %d): %s — auto-passing", iteration, e)
                result = ReflectionResult(
                    score=1.0, passed=True,
                    justification=f"Reflection error: {e} — fail-open",
                    iteration=iteration,
                )
                results.append(result)
                break

            result.iteration = iteration
            results.append(result)
            logger.info(
                "Reflection iteration %d: score=%.2f (threshold=%.2f) passed=%s",
                iteration, result.score, self._threshold, result.passed,
            )

            if result.score >= self._threshold:
                break

            if iteration < self._max_iterations:
                logger.info("Regenerating with feedback: %s", result.feedback[:100])
                try:
                    current = await regenerate_fn(current, result.feedback)
                except Exception as e:
                    logger.warning("Regeneration failed: %s — keeping current output", e)
                    break

        return current, results

    async def _evaluate(self, system_prompt: str, user_prompt: str) -> ReflectionResult:
        """Call LLM and parse the structured response."""
        try:
            response = await self._provider.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=500,
            )
        except TimeoutError:
            logger.warning("LLM timeout during reflection — auto-passing")
            return ReflectionResult(score=1.0, passed=True, justification="LLM timeout — fail-open")
        except Exception as e:
            logger.warning("LLM error during reflection: %s — auto-passing", e)
            return ReflectionResult(score=1.0, passed=True, justification=f"LLM error: {e} — fail-open")

        return self._parse_response(response)

    @staticmethod
    def _parse_response(text: str) -> ReflectionResult:
        """Parse structured reflection response."""
        score = 0.0
        passed = False
        justification = ""
        feedback = ""

        score_match = re.search(r"SCORE:\s*([\d.]+)", text, re.IGNORECASE)
        if score_match:
            try:
                score = float(score_match.group(1))
            except ValueError:
                score = 0.0

        passed_match = re.search(r"PASSED:\s*(yes|no|true|false)", text, re.IGNORECASE)
        if passed_match:
            passed = passed_match.group(1).lower() in ("yes", "true")
        else:
            passed = score >= 0.6

        just_match = re.search(r"JUSTIFICATION:\s*(.+?)(?=FEEDBACK:|$)", text, re.IGNORECASE | re.DOTALL)
        if just_match:
            justification = just_match.group(1).strip()

        feedback_match = re.search(r"FEEDBACK:\s*(.+?)$", text, re.IGNORECASE | re.DOTALL)
        if feedback_match:
            feedback = feedback_match.group(1).strip()

        return ReflectionResult(
            score=score,
            passed=passed,
            justification=justification,
            feedback=feedback,
        )
