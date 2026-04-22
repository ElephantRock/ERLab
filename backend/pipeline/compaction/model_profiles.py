"""Model-aware context window sizes and trigger thresholds."""

from __future__ import annotations

MODEL_CONTEXT_SIZES: dict[str, int] = {
    # OpenAI
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 16_385,
    # Anthropic
    "claude-sonnet-4-20250514": 200_000,
    "claude-sonnet-4": 200_000,
    "claude-haiku-4-5-20251001": 200_000,
    "claude-haiku-4": 200_000,
    "claude-opus-4-7": 200_000,
    # Google
    "gemini-2.0-flash": 1_048_576,
    "gemini-1.5-pro": 2_097_152,
    # Ollama / local
    "llama3": 8_192,
    "llama3.1": 131_072,
    "mistral": 32_000,
    "mixtral": 32_000,
}

DEFAULT_CONTEXT_SIZE = 128_000


def get_context_size(model_name: str) -> int:
    """Look up context window size for a model. Falls back to 128k."""
    # Try exact match first
    if model_name in MODEL_CONTEXT_SIZES:
        return MODEL_CONTEXT_SIZES[model_name]
    # Try prefix match (e.g., "gpt-4o-2024-05-13" matches "gpt-4o")
    for key, size in MODEL_CONTEXT_SIZES.items():
        if model_name.startswith(key):
            return size
    return DEFAULT_CONTEXT_SIZE


def get_trigger_threshold(model_name: str, fraction: float = 0.85) -> int:
    """Return the token count at which compression should trigger."""
    return int(get_context_size(model_name) * fraction)
