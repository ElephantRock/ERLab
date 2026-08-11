"""Simple plugin registry — list and register plugins.

Each plugin is a dict with name, version, description, and enabled flag.
The registry is backed by an in-memory store (can be swapped for DB later).
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, field


@dataclass
class Plugin:
    """A registered plugin."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    enabled: bool = True
    metadata: dict = field(default_factory=dict)


class PluginRegistry:
    """Thread-safe plugin registry."""

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._lock = threading.Lock()

        # Seed with built-in plugins
        self._seed_builtins()

    def _seed_builtins(self) -> None:
        """Register built-in platform plugins."""
        builtins = [
            Plugin(
                name="pdf-export",
                version="1.0.0",
                description="Export research ideas as PDF documents",
                enabled=True,
            ),
            Plugin(
                name="bulk-export",
                version="1.0.0",
                description="Bulk export ideas as a ZIP archive",
                enabled=True,
            ),
            Plugin(
                name="literature-search",
                version="1.0.0",
                description="Search and ingest academic literature",
                enabled=True,
            ),
            Plugin(
                name="knowledge-graph",
                version="1.0.0",
                description="Build and query knowledge graphs from research data",
                enabled=True,
            ),
        ]
        for p in builtins:
            self._plugins[p.name] = p

    def list_plugins(self) -> list[dict]:
        """Return all registered plugins as dicts."""
        with self._lock:
            return [asdict(p) for p in self._plugins.values()]

    def get_plugin(self, name: str) -> dict | None:
        """Return a single plugin by name, or None."""
        with self._lock:
            p = self._plugins.get(name)
            return asdict(p) if p else None

    def install(self, name: str, version: str = "0.1.0", description: str = "") -> dict:
        """Register (install) a new plugin. Returns the plugin dict."""
        with self._lock:
            if name in self._plugins:
                # Update existing
                existing = self._plugins[name]
                existing.version = version
                existing.description = description or existing.description
                return asdict(existing)
            plugin = Plugin(name=name, version=version, description=description)
            self._plugins[name] = plugin
            return asdict(plugin)

    def uninstall(self, name: str) -> bool:
        """Remove a plugin. Returns True if it existed."""
        with self._lock:
            return self._plugins.pop(name, None) is not None


# Singleton registry instance
_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    """Return the global plugin registry."""
    return _registry
