"""Regression tests for resolve_embedding_base_url.

The preflight gate, the ideas novelty route, the semantic cache, and the
capability CLI historically passed ``settings.ollama_base_url`` to the
embedding factory regardless of the configured provider — sending the
LM Studio embedding check to a dead Ollama port and producing a false
"pipeline will run without vector search" warning. The resolver is the
shared precedence rule (mirrors orchestrator/service_registry.py):
explicit embedding_base_url override > provider-specific default
(lmstudio) > ollama_base_url.
"""

import pytest

from backend.pipeline.knowledge.embedding_providers import resolve_embedding_base_url


class _Settings:
    def __init__(
        self,
        *,
        embedding_base_url: str = "",
        lmstudio_base_url: str = "http://100.64.0.2:1234",
        ollama_base_url: str = "http://localhost:11434",
    ):
        self.embedding_base_url = embedding_base_url
        self.lmstudio_base_url = lmstudio_base_url
        self.ollama_base_url = ollama_base_url


class TestResolveEmbeddingBaseUrl:
    def test_explicit_override_wins_and_normalizes_v1(self):
        s = _Settings(embedding_base_url="http://100.64.0.2:1234")
        assert resolve_embedding_base_url(s, "lmstudio") == "http://100.64.0.2:1234/v1"

    def test_explicit_override_keeps_existing_v1(self):
        s = _Settings(embedding_base_url="http://host:1234/v1/")
        assert resolve_embedding_base_url(s, "lmstudio") == "http://host:1234/v1"

    def test_lmstudio_provider_uses_lmstudio_url_with_v1(self):
        s = _Settings()
        assert resolve_embedding_base_url(s, "lmstudio") == "http://100.64.0.2:1234/v1"

    def test_ollama_provider_falls_back_to_ollama_url(self):
        s = _Settings()
        assert resolve_embedding_base_url(s, "ollama") == "http://localhost:11434"

    def test_unknown_provider_falls_back_to_ollama_url(self):
        s = _Settings()
        assert resolve_embedding_base_url(s, "gemini") == "http://localhost:11434"

    def test_blank_override_does_not_shadow_lmstudio(self):
        s = _Settings(embedding_base_url="")
        assert resolve_embedding_base_url(s, "lmstudio") == "http://100.64.0.2:1234/v1"

    def test_lmstudio_url_missing_v1_gets_appended(self):
        s = _Settings(lmstudio_base_url="http://localhost:1234/")
        assert resolve_embedding_base_url(s, "lmstudio") == "http://localhost:1234/v1"

    def test_none_ollama_url_returns_none_for_non_lmstudio(self):
        s = _Settings()
        s.ollama_base_url = None
        assert resolve_embedding_base_url(s, "ollama") is None

    def test_settings_without_embedding_base_url_attr(self):
        class _Legacy:
            lmstudio_base_url = "http://lm:1234"
            ollama_base_url = "http://ollama:11434"

        s = _Legacy()
        assert resolve_embedding_base_url(s, "lmstudio") == "http://lm:1234/v1"
        assert resolve_embedding_base_url(s, "ollama") == "http://ollama:11434"

    @pytest.mark.parametrize("provider", ["LMStudio", " lmstudio "])
    def test_provider_name_normalized(self, provider):
        s = _Settings()
        assert resolve_embedding_base_url(s, provider) == "http://100.64.0.2:1234/v1"
