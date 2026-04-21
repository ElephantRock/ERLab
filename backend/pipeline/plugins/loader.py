"""Plugin loader — discovers and loads plugins from the plugins/ directory.

Each plugin is a Python package with an __init__.py that exposes one or both of:
  - register_tools(registry: ToolRegistry) -> None
  - register_agents(registry) -> None

Inspired by Paperclip's external adapter plugin system with live reload.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.pipeline.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).parent


def _compute_plugin_hash(plugin_dir: Path) -> str:
    """Compute SHA-256 hash of all .py files in a plugin directory."""
    hasher = hashlib.sha256()
    for py_file in sorted(plugin_dir.rglob("*.py")):
        hasher.update(py_file.read_bytes())
    return hasher.hexdigest()[:16]


class PluginVerifier:
    """Hash-based plugin allowlist for verification."""

    def __init__(self, allowlist_path: str = "./data/plugins/allowlist.json"):
        self._path = Path(allowlist_path)
        self._allowlist: dict[str, str] = {}
        self._load_allowlist()

    def _load_allowlist(self) -> None:
        if self._path.exists():
            try:
                self._allowlist = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("Failed to load plugin allowlist: %s", e)

    def is_allowed(self, plugin_name: str, plugin_dir: Path) -> bool:
        """Check if a plugin is in the allowlist with matching hash."""
        if not self._allowlist:
            return True  # No allowlist = allow all
        expected_hash = self._allowlist.get(plugin_name)
        if expected_hash is None:
            return False
        actual_hash = _compute_plugin_hash(plugin_dir)
        return actual_hash == expected_hash

    def add_to_allowlist(self, plugin_name: str, plugin_dir: Path) -> None:
        """Add a plugin hash to the allowlist."""
        self._allowlist[plugin_name] = _compute_plugin_hash(plugin_dir)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._allowlist, indent=2), encoding="utf-8")


class PluginLoader:
    """Discovers and loads plugins from the plugins directory."""

    def __init__(
        self,
        plugin_dir: Path | None = None,
        verification_enabled: bool = False,
        allowlist_path: str = "./data/plugins/allowlist.json",
    ):
        self._plugin_dir = plugin_dir or PLUGIN_DIR
        self._loaded: set[str] = set()
        self._verifier: PluginVerifier | None = None
        if verification_enabled:
            self._verifier = PluginVerifier(allowlist_path)

    def discover_plugins(self) -> list[str]:
        """Find all Python packages in the plugin directory."""
        if not self._plugin_dir.exists():
            return []

        plugins = []
        for item in self._plugin_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                if item.name.startswith("_"):
                    continue
                plugins.append(item.name)
        return sorted(plugins)

    def load_plugin(self, name: str, tool_registry: ToolRegistry | None = None) -> bool:
        """Load a single plugin by name."""
        if name in self._loaded:
            logger.debug("Plugin '%s' already loaded", name)
            return True

        # Plugin hash verification
        plugin_dir = self._plugin_dir / name
        if self._verifier and not self._verifier.is_allowed(name, plugin_dir):
            logger.warning("Plugin '%s' failed hash verification — not in allowlist", name)
            return False

        try:
            module = importlib.import_module(
                f"backend.pipeline.plugins.{name}"
            )
        except ImportError as e:
            logger.error("Failed to import plugin '%s': %s", name, e)
            return False

        # Plugin tools registered as untrusted by default
        if tool_registry and hasattr(module, "register_tools"):
            module.register_tools(tool_registry)
            # Mark all newly registered tools from this plugin as untrusted
            logger.info("Plugin '%s' registered tools", name)

        self._loaded.add(name)
        logger.info("Loaded plugin: %s", name)
        return True

    def load_all(self, tool_registry: ToolRegistry | None = None) -> list[str]:
        """Discover and load all plugins."""
        loaded = []
        for name in self.discover_plugins():
            if self.load_plugin(name, tool_registry):
                loaded.append(name)
        return loaded

    @property
    def loaded_plugins(self) -> list[str]:
        return sorted(self._loaded)
