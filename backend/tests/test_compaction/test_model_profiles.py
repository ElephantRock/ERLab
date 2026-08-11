"""Tests for model context size profiles."""

from backend.pipeline.compaction.model_profiles import (
    DEFAULT_CONTEXT_SIZE,
    get_context_size,
    get_trigger_threshold,
)


class TestGetContextSize:
    def test_exact_match_gpt4o(self):
        assert get_context_size("gpt-4o") == 128_000

    def test_exact_match_claude(self):
        assert get_context_size("claude-sonnet-4-20250514") == 200_000

    def test_exact_match_gemini(self):
        assert get_context_size("gemini-2.0-flash") == 1_048_576

    def test_exact_match_llama(self):
        assert get_context_size("llama3") == 8_192

    def test_prefix_match(self):
        assert get_context_size("gpt-4o-2024-05-13") == 128_000

    def test_unknown_model_fallback(self):
        assert get_context_size("unknown-model-xyz") == DEFAULT_CONTEXT_SIZE


class TestGetTriggerThreshold:
    def test_default_fraction(self):
        threshold = get_trigger_threshold("gpt-4o")
        assert threshold == int(128_000 * 0.85)

    def test_custom_fraction(self):
        threshold = get_trigger_threshold("gpt-4o", fraction=0.5)
        assert threshold == 64_000

    def test_unknown_model(self):
        threshold = get_trigger_threshold("unknown", fraction=0.9)
        assert threshold == int(DEFAULT_CONTEXT_SIZE * 0.9)
