"""Regression (Case 3B specimen): structured_output must retry on
empty responses instead of returning an empty dict on the first coin
flip.

Local grammatically-constrained serving (LM Studio json_schema)
intermittently returns empty content at a reproduced 40-75% rate while
plain completions stay healthy. Every prior successful run carried
~19 "Empty LLM response" warnings and survived only because the
empties missed load-bearing calls; in run_20260817_060404 they hit
gap-quality scoring and the Decision Gate correctly aborted at 0.00.

The fix is a bounded whole-chain retry in OpenAIProvider.
structured_output; these tests prove recovery and boundedness.
"""
from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.providers.openai_provider import OpenAIProvider


def _provider_with_contents(contents: list[str]) -> OpenAIProvider:
    p = OpenAIProvider(api_key="test", base_url="http://127.0.0.1:9/")
    client = MagicMock()
    create = AsyncMock(
        side_effect=[
            MagicMock(
                choices=[MagicMock(
                    message=MagicMock(content=c),
                )]
            )
            for c in contents
        ]
    )
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = create
    p._client = client
    return p


SCHEMA = {
    "type": "object",
    "properties": {"x": {"type": "integer"}},
    "required": ["x"],
}


class TestRetryOnEmpty:
    def test_recovers_after_empties(self):
        p = _provider_with_contents(["", "", '{"x": 1}'])
        result = asyncio.run(
            p.structured_output([{"role": "user", "content": "q"}], SCHEMA)
        )
        assert result == {"x": 1}
        assert p._client.chat.completions.create.await_count == 3

    def test_bounded_after_all_empty(self):
        # 3 retries + 1 initial = 4 whole-chain attempts max; each
        # attempt may consume up to 2 transport calls (dialect try +
        # plain fallback), so 8 empties exhaust every path and the
        # empty dict is returned.
        p = _provider_with_contents([""] * 8 + ['{"x": 9}'])
        result = asyncio.run(
            p.structured_output([{"role": "user", "content": "q"}], SCHEMA)
        )
        assert result == {}
        assert p._client.chat.completions.create.await_count == 8

    def test_first_try_success_no_retry(self):
        p = _provider_with_contents(['{"x": 2}'])
        result = asyncio.run(
            p.structured_output([{"role": "user", "content": "q"}], SCHEMA)
        )
        assert result == {"x": 2}
        assert p._client.chat.completions.create.await_count == 1

    def test_falsy_parsed_results_also_retry(self):
        # Content present but unparseable is treated the same as empty:
        # the whole dialect chain runs, returns {}, and the wrapper
        # retries.
        p = _provider_with_contents(["not json", '{"x": 5}'])
        result = asyncio.run(
            p.structured_output([{"role": "user", "content": "q"}], SCHEMA)
        )
        assert result == {"x": 5}


class TestRetryOnEmptyUsagePath:
    """PR #27 review P1: the orchestrator gateway calls
    structured_output_with_usage(); the retry must live there too."""

    def _usage_provider_with(self, structured_results):
        p = OpenAIProvider(api_key="test", base_url="http://127.0.0.1:9/")
        # Bypass the whole once-chain: stub the inner once-method.
        calls = {"n": 0}

        async def fake_once(messages, schema, temperature=0.3,
                            max_tokens=8192, stage="", run_id=None):
            from backend.providers.base import LLMResponse
            idx = min(calls["n"], len(structured_results) - 1)
            calls["n"] += 1
            return LLMResponse(
                content="", structured=structured_results[idx],
                input_tokens=1, output_tokens=1, served_model="t",
            )

        p._structured_output_with_usage_once = fake_once
        return p, calls

    def test_usage_path_recovers_after_empties(self):
        p, calls = self._usage_provider_with([{}, {}, {"x": 1}])
        resp = asyncio.run(
            p.structured_output_with_usage(
                [{"role": "user", "content": "q"}], SCHEMA,
            )
        )
        assert resp.structured == {"x": 1}
        assert calls["n"] == 3

    def test_usage_path_bounded(self):
        p, calls = self._usage_provider_with([{}])
        resp = asyncio.run(
            p.structured_output_with_usage(
                [{"role": "user", "content": "q"}], SCHEMA,
            )
        )
        assert resp.structured == {}
        assert calls["n"] == 4  # 1 initial + 3 retries
