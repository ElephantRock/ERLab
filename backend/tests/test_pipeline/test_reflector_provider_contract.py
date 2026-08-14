"""Regression (run 2712): ReflectionStage._evaluate must call the
provider's messages-list interface.

It previously passed system_prompt=/user_prompt= kwargs, which
LLMProvider.complete() (and ResilientProvider.complete()) reject with a
TypeError. Every live reflection call then fail-opened to score=1.0
without ever consuming a provider response.
"""
from __future__ import annotations

import asyncio
import sys
from unittest.mock import MagicMock

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.reflection.reflector import ReflectionStage

GOOD_RESPONSE = (
    "SCORE: 0.85\n"
    "PASSED: yes\n"
    "JUSTIFICATION: grounded and specific\n"
    "FEEDBACK: none"
)

LOW_RESPONSE = (
    "SCORE: 0.30\n"
    "PASSED: no\n"
    "JUSTIFICATION: too vague\n"
    "FEEDBACK: add dataset detail"
)


class RecordingProvider:
    """Provider implementing ONLY the canonical complete() signature —
    no **kwargs escape hatch. The old system_prompt=/user_prompt= call
    raises TypeError against this class, exactly like ResilientProvider."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list[tuple] = []

    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        self.calls.append((messages, temperature, max_tokens))
        return self._responses.pop(0)


class TestEvaluateUsesMessagesInterface:
    def test_call_shape_is_messages_list(self):
        provider = RecordingProvider([GOOD_RESPONSE])
        stage = ReflectionStage(provider=provider)
        asyncio.run(stage._evaluate("SYS-PROMPT", "USER-CONTENT"))

        assert len(provider.calls) == 1
        messages, temperature, max_tokens = provider.calls[0]
        assert isinstance(messages, list)
        assert {"role": "system", "content": "SYS-PROMPT"} in messages
        assert {"role": "user", "content": "USER-CONTENT"} in messages
        assert max_tokens == 500

    def test_response_is_consumed_not_fail_open(self):
        provider = RecordingProvider([GOOD_RESPONSE])
        stage = ReflectionStage(provider=provider)
        result = asyncio.run(stage._evaluate("SYS", "USER"))

        assert result.score == 0.85
        assert result.passed is True
        assert result.justification == "grounded and specific"
        assert "fail-open" not in result.justification

    def test_low_score_parses_and_fails(self):
        provider = RecordingProvider([LOW_RESPONSE])
        stage = ReflectionStage(provider=provider)
        result = asyncio.run(stage._evaluate("SYS", "USER"))

        assert result.score == 0.30
        assert result.passed is False
        assert result.feedback == "add dataset detail"


class TestReflectGapsConsumesResponse:
    def test_reflect_gaps_reaches_provider(self):
        provider = RecordingProvider([GOOD_RESPONSE])
        stage = ReflectionStage(provider=provider)

        gap = MagicMock()
        gap.title = "Calibration gap"
        gap.description = "No study of calibration under shift"
        result = asyncio.run(stage.reflect_gaps([gap], query="ML"))

        assert len(provider.calls) == 1
        user_msg = provider.calls[0][0][-1]
        assert user_msg["role"] == "user"
        assert "Calibration gap" in user_msg["content"]
        assert result.score == 0.85

    def test_reflect_with_retry_regenerates_on_low_score(self):
        """A low score must trigger regeneration and a second evaluation.
        The old fail-open path broke immediately at score=1.0."""
        provider = RecordingProvider([LOW_RESPONSE, GOOD_RESPONSE])
        stage = ReflectionStage(provider=provider, threshold=0.6, max_iterations=3)

        regenerations: list[tuple] = []

        async def regenerate(content, feedback):
            regenerations.append((content, feedback))
            return content

        gap = MagicMock()
        gap.title = "G"
        gap.description = "D"

        async def reflect_fn(content):
            return await stage.reflect_gaps(content, query="q")

        _, results = asyncio.run(
            stage.reflect_with_retry([gap], reflect_fn, regenerate)
        )

        assert len(provider.calls) == 2
        assert len(regenerations) == 1
        assert regenerations[0][1] == "add dataset detail"
        assert results[0].score == 0.30
        assert results[1].score == 0.85
