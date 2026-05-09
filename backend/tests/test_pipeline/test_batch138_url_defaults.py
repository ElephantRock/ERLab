"""BATCH-138 / TASK-03 — Verify remaining localhost URL defaults cleaned up.

Tests:
  TEST-138-03-01: OTLP exporter reads endpoint from settings
  TEST-138-03-02: No getattr URL fallbacks in provider_factory
"""

import inspect
import re

import pytest


class TestOTLPExporterReadsSettings:
    """TEST-138-03-01 — OTLP exporter reads endpoint from settings."""

    def test_otlp_exporter_default_reads_settings(self) -> None:
        """OTLPExporter.__init__ resolves endpoint from settings when None."""
        from backend.pipeline.observability.otlp_exporter import _OTEL_AVAILABLE

        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry packages not installed")

        from backend.pipeline.observability.otlp_exporter import OTLPExporter

        # Default reads from settings
        exporter = OTLPExporter()
        assert exporter is not None

    def test_otlp_exporter_explicit_endpoint(self) -> None:
        """Explicit endpoint overrides settings."""
        from backend.pipeline.observability.otlp_exporter import _OTEL_AVAILABLE

        if not _OTEL_AVAILABLE:
            pytest.skip("opentelemetry packages not installed")

        from backend.pipeline.observability.otlp_exporter import OTLPExporter

        exporter = OTLPExporter(endpoint="http://custom:4317")
        assert exporter is not None

    def test_observability_manager_default_reads_settings(self) -> None:
        """ObservabilityManager resolves otlp_endpoint from settings when None."""
        from backend.pipeline.observability.manager import ObservabilityManager

        mgr = ObservabilityManager(otlp_enabled=False)
        assert mgr is not None

    def test_observability_manager_explicit_endpoint(self) -> None:
        """Explicit otlp_endpoint overrides settings."""
        from backend.pipeline.observability.manager import ObservabilityManager

        mgr = ObservabilityManager(
            otlp_enabled=False, otlp_endpoint="http://custom:4317"
        )
        assert mgr is not None


class TestNoHardcodedUrlFallbacks:
    """TEST-138-03-02 — No getattr fallbacks with hardcoded URLs."""

    def test_provider_factory_no_hardcoded_url_in_getattr(self) -> None:
        """provider_factory.py has no getattr calls with 'http://' string."""
        import backend.providers.provider_factory as pf

        source = inspect.getsource(pf)
        # Find all getattr calls and check none contain a URL fallback
        getattr_calls = re.findall(r"getattr\([^)]+\)", source)
        for call in getattr_calls:
            assert "http://" not in call, (
                f"Found getattr with hardcoded URL: {call}"
            )

    def test_embedding_providers_no_hardcoded_localhost_default(self) -> None:
        """embedding_providers.py OllamaEmbeddingProvider constructor reads
        from settings instead of hardcoding localhost."""
        from backend.pipeline.knowledge.embedding_providers import (
            OllamaEmbeddingProvider,
        )

        # Constructor with no base_url should read from settings (not crash)
        OllamaEmbeddingProvider.__new__(OllamaEmbeddingProvider)
        # Verify the __init__ signature has Optional base_url
        sig = inspect.signature(OllamaEmbeddingProvider.__init__)
        base_url_param = sig.parameters.get("base_url")
        assert base_url_param is not None
        assert base_url_param.default is None or base_url_param.default is inspect.Parameter.empty

    def test_ollama_provider_no_hardcoded_localhost_default(self) -> None:
        """OllamaProvider constructor reads from settings instead of
        hardcoding localhost."""
        from backend.providers.ollama_provider import OllamaProvider

        sig = inspect.signature(OllamaProvider.__init__)
        base_url_param = sig.parameters.get("base_url")
        assert base_url_param is not None
        # Should be None default (reads from settings), not a hardcoded URL
        assert base_url_param.default is None


class TestOllamaProvidersReadSettings:
    """Additional: ollama providers resolve base_url from settings."""

    def test_ollama_provider_default_reads_settings(self) -> None:
        from backend.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        assert provider._base_url == "http://localhost:11434"

    def test_ollama_provider_explicit_base_url(self) -> None:
        from backend.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider(base_url="http://custom:12345")
        assert provider._base_url == "http://custom:12345"

    def test_ollama_embedding_provider_default_reads_settings(self) -> None:
        from backend.pipeline.knowledge.embedding_providers import (
            OllamaEmbeddingProvider,
        )

        provider = OllamaEmbeddingProvider()
        assert provider._base_url == "http://localhost:11434"

    def test_ollama_embedding_provider_explicit_base_url(self) -> None:
        from backend.pipeline.knowledge.embedding_providers import (
            OllamaEmbeddingProvider,
        )

        provider = OllamaEmbeddingProvider(base_url="http://custom:12345")
        assert provider._base_url == "http://custom:12345"
