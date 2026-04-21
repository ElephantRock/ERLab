"""Tests for API key validation in provider_factory."""

from unittest.mock import MagicMock

import pytest

from backend.providers.provider_factory import _validate_api_key


class TestApiKeyValidation:
    def test_openai_missing_key_raises(self):
        settings = MagicMock()
        settings.openai_api_key = None
        with pytest.raises(SystemExit, match="EROCK_OPENAI_API_KEY"):
            _validate_api_key("openai", settings)

    def test_openai_empty_key_raises(self):
        settings = MagicMock()
        settings.openai_api_key = "  "
        with pytest.raises(SystemExit, match="EROCK_OPENAI_API_KEY"):
            _validate_api_key("openai", settings)

    def test_ollama_no_key_needed(self):
        settings = MagicMock()
        _validate_api_key("ollama", settings)  # should not raise

    def test_anthropic_missing_key_raises(self):
        settings = MagicMock()
        settings.anthropic_api_key = None
        with pytest.raises(SystemExit, match="EROCK_ANTHROPIC_API_KEY"):
            _validate_api_key("anthropic", settings)

    def test_gemini_empty_key_raises(self):
        settings = MagicMock()
        settings.gemini_api_key = ""
        with pytest.raises(SystemExit, match="EROCK_GEMINI_API_KEY"):
            _validate_api_key("gemini", settings)
