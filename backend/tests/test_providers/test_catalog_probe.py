"""Tests for catalog probe functions.

Verifies that probe_openai_compatible() correctly reads extended metadata
from OpenAI-compatible servers that return richer fields than stock OpenAI.

Regression coverage for the bug where context_length, is_loaded, and
capabilities were ignored — causing all models to default to 8192 ctx
and triggering cascading graceful-degradation failures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.providers.catalog import (
    ModelCatalog,
    ModelInfo,
    probe_openai_compatible,
)

# ---------------------------------------------------------------------------
# Simulated API responses
# ---------------------------------------------------------------------------

# Response from a proxy that returns rich metadata (LM Studio proxy, LocalAI)
RICH_PROXY_RESPONSE = {
    "data": [
        {
            "id": "qwen/qwen3-4b-2507",
            "parameter_count": "4B",
            "context_length": 262144,
            "quantization": "Q4_K_M",
            "capabilities": {
                "json_mode": True,
                "tools": True,
                "vision": False,
                "thinking": False,
            },
            "is_loaded": True,
            "size_gb": 2.33,
            "display_name": "Qwen3 4B 2507",
        },
        {
            "id": "arliai_glm-4.5-air-derestricted",
            "parameter_count": "?",
            "context_length": 4096,
            "quantization": "None",
            "capabilities": {
                "json_mode": True,
                "tools": False,
                "vision": False,
                "thinking": False,
            },
            "is_loaded": False,
            "size_gb": 0.21,
            "display_name": "ArliAI GLM 4.5 Air",
        },
    ]
}

# Response from a stock OpenAI endpoint (minimal fields)
STOCK_OPENAI_RESPONSE = {
    "data": [
        {"id": "gpt-4o", "object": "model", "created": 1234567890, "owned_by": "openai"},
        {"id": "gpt-4o-mini", "object": "model", "created": 1234567890, "owned_by": "openai"},
    ]
}


def _mock_response(data: dict, status: int = 200) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status
    mock.json.return_value = data
    mock.raise_for_status = MagicMock()
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestProbeOpenAICompatible:
    """Tests for probe_openai_compatible()."""

    @pytest.mark.asyncio
    async def test_reads_context_length_from_proxy(self):
        """Context length from extended metadata is used, not defaulted to 8192."""
        with patch("backend.providers.catalog.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=_mock_response(RICH_PROXY_RESPONSE))
            mock_cls.return_value = mock_client

            models = await probe_openai_compatible("http://localhost:8766")

        qwen = next(m for m in models if "qwen3-4b" in m.model_id)
        assert qwen.context_length == 262144  # NOT 8192!

    @pytest.mark.asyncio
    async def test_reads_is_loaded_from_proxy(self):
        """is_loaded flag from proxy response is respected."""
        with patch("backend.providers.catalog.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=_mock_response(RICH_PROXY_RESPONSE))
            mock_cls.return_value = mock_client

            models = await probe_openai_compatible("http://localhost:8766")

        qwen = next(m for m in models if "qwen3-4b" in m.model_id)
        arliai = next(m for m in models if "arliai" in m.model_id)
        assert qwen.is_loaded is True
        assert arliai.is_loaded is False

    @pytest.mark.asyncio
    async def test_reads_capabilities(self):
        """Capabilities dict is parsed for tools, json_mode, thinking."""
        with patch("backend.providers.catalog.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=_mock_response(RICH_PROXY_RESPONSE))
            mock_cls.return_value = mock_client

            models = await probe_openai_compatible("http://localhost:8766")

        qwen = next(m for m in models if "qwen3-4b" in m.model_id)
        assert qwen.supports_json_mode is True
        assert qwen.supports_tools is True
        assert qwen.supports_thinking is False

    @pytest.mark.asyncio
    async def test_reads_parameter_count_and_quantization(self):
        """Parameter count and quantization are read from extended metadata."""
        with patch("backend.providers.catalog.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=_mock_response(RICH_PROXY_RESPONSE))
            mock_cls.return_value = mock_client

            models = await probe_openai_compatible("http://localhost:8766")

        qwen = next(m for m in models if "qwen3-4b" in m.model_id)
        assert qwen.parameter_count == "4B"
        assert qwen.quantization == "Q4_K_M"

    @pytest.mark.asyncio
    async def test_reads_size_gb(self):
        """size_gb field is converted to bytes."""
        with patch("backend.providers.catalog.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=_mock_response(RICH_PROXY_RESPONSE))
            mock_cls.return_value = mock_client

            models = await probe_openai_compatible("http://localhost:8766")

        qwen = next(m for m in models if "qwen3-4b" in m.model_id)
        assert qwen.size_bytes > 2e9  # ~2.33 GB
        assert qwen.size_bytes < 3e9

    @pytest.mark.asyncio
    async def test_stock_openai_defaults_preserved(self):
        """Stock OpenAI endpoints (no extended fields) still work with defaults."""
        with patch("backend.providers.catalog.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=_mock_response(STOCK_OPENAI_RESPONSE))
            mock_cls.return_value = mock_client

            models = await probe_openai_compatible("https://api.openai.com")

        assert len(models) == 2
        gpt4o = models[0]
        # Falls back to defaults
        assert gpt4o.context_length == 8192
        assert gpt4o.is_loaded is True  # assume available
        assert gpt4o.parameter_count == "?"

    @pytest.mark.asyncio
    async def test_context_length_field_name_variants(self):
        """All context_length field names are tried in order."""
        variants = [
            {"data": [{"id": "m1", "max_model_len": 65536}]},
            {"data": [{"id": "m2", "max_context_length": 32768}]},
            {"data": [{"id": "m3", "context_length": 16384}]},
        ]
        for i, resp_data in enumerate(variants):
            expected = [65536, 32768, 16384][i]
            with patch("backend.providers.catalog.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.get = AsyncMock(return_value=_mock_response(resp_data))
                mock_cls.return_value = mock_client

                models = await probe_openai_compatible("http://test")
                assert models[0].context_length == expected


class TestModelSelectorFallback:
    """Tests for ModelSelector graceful degradation preferring loaded models."""

    def test_fallback_prefers_loaded_model(self):
        """When no model meets requirements, loaded models are preferred."""
        from backend.providers.selector import ModelSelector

        # Create two models: one loaded, one not
        loaded = ModelInfo(
            model_id="qwen/qwen3-4b",
            provider_type="openai_compatible",
            endpoint_url="http://localhost/v1",
            context_length=8192,
            is_loaded=True,
            health_status="healthy",
        )
        unloaded = ModelInfo(
            model_id="arliai_big",
            provider_type="openai_compatible",
            endpoint_url="http://localhost/v1",
            context_length=8192,
            is_loaded=False,
            health_status="healthy",
        )

        catalog = ModelCatalog([])
        catalog._models = {loaded.model_id: loaded, unloaded.model_id: unloaded}
        selector = ModelSelector(catalog, gpu=None)

        # No model meets 999999 context requirement → graceful degradation
        result = selector.select("paper_synthesis")  # min_ctx=32768
        assert result is not None
        assert result.model_id == "qwen/qwen3-4b"  # loaded one preferred

    def test_fallback_prefers_configured_model(self):
        """Configured preferred_model wins among loaded models."""
        from backend.providers.selector import ModelSelector

        model_a = ModelInfo(
            model_id="model_a",
            provider_type="openai_compatible",
            endpoint_url="http://localhost/v1",
            context_length=8192,
            is_loaded=True,
            health_status="healthy",
        )
        model_b = ModelInfo(
            model_id="preferred_model",
            provider_type="openai_compatible",
            endpoint_url="http://localhost/v1",
            context_length=8192,
            is_loaded=True,
            health_status="healthy",
        )

        catalog = ModelCatalog([])
        catalog._models = {model_a.model_id: model_a, model_b.model_id: model_b}
        selector = ModelSelector(
            catalog, gpu=None, preferred_model="preferred_model",
        )

        result = selector.select("paper_synthesis")
        assert result is not None
        assert result.model_id == "preferred_model"
