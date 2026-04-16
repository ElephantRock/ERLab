"""Factory for creating LLM provider instances."""

from backend.config import get_settings
from backend.providers.base import LLMProvider


_REGISTRY: dict[str, type[LLMProvider]] = {}


def _auto_register():
    """Lazily register all built-in providers."""
    if _REGISTRY:
        return
    from backend.providers.anthropic_provider import AnthropicProvider
    from backend.providers.gemini_provider import GeminiProvider
    from backend.providers.ollama_provider import OllamaProvider
    from backend.providers.openai_provider import OpenAIProvider

    _REGISTRY["openai"] = OpenAIProvider
    _REGISTRY["anthropic"] = AnthropicProvider
    _REGISTRY["gemini"] = GeminiProvider
    _REGISTRY["ollama"] = OllamaProvider


def register_provider(name: str, cls: type[LLMProvider]) -> None:
    _REGISTRY[name] = cls


def create_provider(name: str | None = None) -> LLMProvider:
    """Create and return a configured LLM provider.

    If name is None, uses the default_provider from settings.
    """
    _auto_register()
    settings = get_settings()
    name = name or settings.default_provider

    if name not in _REGISTRY:
        raise ValueError(f"Unknown provider: {name}. Available: {list(_REGISTRY.keys())}")

    cls = _REGISTRY[name]

    if name == "openai":
        return cls(
            api_key=settings.openai_api_key or "",
            model=settings.openai_model,
            embedding_model=settings.embedding_model,
        )
    elif name == "anthropic":
        return cls(
            api_key=settings.anthropic_api_key or "",
            model=settings.anthropic_model,
            embedding_model=settings.embedding_model,
        )
    elif name == "gemini":
        return cls(
            api_key=settings.gemini_api_key or "",
            model=settings.gemini_model,
        )
    elif name == "ollama":
        return cls(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
    else:
        return cls()
