"""Registry for pipeline strategy configurations."""
from __future__ import annotations

from .models import PipelineStrategy, StrategyConfig


class StrategyRegistry:
    """Central registry for pipeline strategies.

    Strategies are registered by name and can be retrieved at pipeline start.
    The registry is populated with presets at import time via ``register_presets()``.
    """

    def __init__(self) -> None:
        self._strategies: dict[str, StrategyConfig] = {}

    def register(self, config: StrategyConfig) -> None:
        """Register or overwrite a strategy configuration."""
        key = config.name.value if isinstance(config.name, PipelineStrategy) else config.name
        self._strategies[key] = config

    def get(self, name: str) -> StrategyConfig:
        """Retrieve a strategy by name.

        Raises:
            ValueError: If no strategy with the given name is registered.
        """
        if name not in self._strategies:
            valid = ", ".join(sorted(self._strategies.keys()))
            raise ValueError(
                f"Unknown pipeline strategy '{name}'. Valid strategies: {valid}"
            )
        return self._strategies[name]

    def list_all(self) -> list[StrategyConfig]:
        """Return all registered strategies."""
        return list(self._strategies.values())

    def has(self, name: str) -> bool:
        """Check if a strategy is registered."""
        return name in self._strategies

    def clear(self) -> None:
        """Remove all registered strategies."""
        self._strategies.clear()


# ── Module-level singleton ────────────────────────────────
_default_registry: StrategyRegistry | None = None


def get_default_registry() -> StrategyRegistry:
    """Return the global default registry, creating and populating it if needed."""
    global _default_registry
    if _default_registry is None:
        _default_registry = StrategyRegistry()
        from .presets import register_presets
        register_presets(_default_registry)
    return _default_registry
