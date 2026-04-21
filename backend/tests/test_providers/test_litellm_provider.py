"""Tests for LiteLLM provider and factory fallback routing."""

import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Create a mock litellm module so the lazy import in LiteLLMProvider works
_mock_litellm = MagicMock()
_mock_litellm.acompletion = AsyncMock()
_mock_litellm.aembedding = AsyncMock()
sys.modules.setdefault("litellm", _mock_litellm)

from backend.providers.litellm_provider import LiteLLMProvider


def _run(coro):
    return asyncio.run(coro)


def _mock_completion_response(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _mock_embedding_response(embeddings: list[list[float]]):
    data = [{"embedding": e} for e in embeddings]
    resp = MagicMock()
    resp.data = data
    return resp


class TestLiteLLMProvider:
    def test_provider_name(self):
        assert LiteLLMProvider(model="gpt-4o").provider_name == "litellm"

    def test_default_model(self):
        assert LiteLLMProvider(model="claude-3-opus").default_model == "claude-3-opus"

    def test_complete(self):
        p = LiteLLMProvider(model="gpt-4o", api_key="test-key")
        mock_resp = _mock_completion_response("Hello world")
        _mock_litellm.acompletion = AsyncMock(return_value=mock_resp)

        result = _run(p.complete(messages=[{"role": "user", "content": "hi"}]))
        assert result == "Hello world"
        _mock_litellm.acompletion.assert_awaited_once()

    def test_complete_stream(self):
        p = LiteLLMProvider(model="gpt-4o")

        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "Hello"

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = " world"

        async def mock_stream(*args, **kwargs):
            for chunk in [chunk1, chunk2]:
                yield chunk

        # litellm.acompletion returns the async generator directly (not awaited)
        _mock_litellm.acompletion = mock_stream
        chunks = []

        async def collect():
            async for c in p.complete_stream(messages=[{"role": "user", "content": "hi"}]):
                chunks.append(c)

        asyncio.run(collect())
        assert "".join(chunks) == "Hello world"

    def test_structured_output(self):
        p = LiteLLMProvider(model="gpt-4o")
        expected = {"queries": ["q1", "q2"]}
        mock_resp = _mock_completion_response(json.dumps(expected))
        _mock_litellm.acompletion = AsyncMock(return_value=mock_resp)

        result = _run(
            p.structured_output(
                messages=[{"role": "user", "content": "test"}],
                schema={},
            )
        )
        assert result == expected

    def test_embed(self):
        p = LiteLLMProvider(model="text-embedding-3-small")
        embeddings = [[0.1, 0.2], [0.3, 0.4]]
        mock_resp = _mock_embedding_response(embeddings)
        _mock_litellm.aembedding = AsyncMock(return_value=mock_resp)

        result = _run(p.embed(["hello", "world"]))
        assert result == embeddings


class TestProviderFactoryLiteLLM:
    """Tests for the ProviderRegistry fallback routing to LiteLLM."""

    def test_litellm_registered_in_registry(self):
        from backend.providers.base import LLMProvider
        from backend.providers.litellm_provider import LiteLLMProvider

        assert issubclass(LiteLLMProvider, LLMProvider)

    def test_fallback_for_unknown_model(self):
        with patch("backend.providers.provider_factory.get_settings") as mock_settings:
            s = MagicMock()
            s.default_provider = "cohere/command-r"
            s.litellm_fallback_enabled = True
            s.openai_api_key = "test-key"
            mock_settings.return_value = s

            import backend.providers.provider_factory as pf

            # Save and replace the singleton registry
            old_registry = pf._registry
            try:
                reg = pf.ProviderRegistry()
                reg._providers.clear()
                reg._providers["litellm"] = LiteLLMProvider
                pf._registry = reg

                provider = pf.create_provider("cohere/command-r")
                assert provider.provider_name == "litellm"
                assert provider.default_model == "cohere/command-r"
            finally:
                pf._registry = old_registry

    def test_no_fallback_when_disabled(self):
        with patch("backend.providers.provider_factory.get_settings") as mock_settings:
            s = MagicMock()
            s.default_provider = "unknown-model"
            s.litellm_fallback_enabled = False
            mock_settings.return_value = s

            import backend.providers.provider_factory as pf

            old_registry = pf._registry
            try:
                reg = pf.ProviderRegistry()
                reg._providers.clear()
                pf._registry = reg

                try:
                    pf.create_provider("unknown-model")
                    assert False, "Should have raised ValueError"
                except ValueError as e:
                    assert "Unknown provider" in str(e)
            finally:
                pf._registry = old_registry
