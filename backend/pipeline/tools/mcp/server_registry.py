"""MCP server registry — YAML-based server configuration."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from backend.pipeline.tools.mcp.models import MCPServerConfig

logger = logging.getLogger(__name__)


class MCPServerRegistry:
    """Loads and validates MCP server configurations from YAML."""

    def __init__(self, config_path: str = "./mcp_servers.yaml") -> None:
        self._path = Path(config_path)
        self._servers: dict[str, MCPServerConfig] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            logger.info("MCP server config not found: %s — no MCP servers configured", self._path)
            return

        try:
            data = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("Failed to parse MCP server config: %s", e)
            return

        if not data or "servers" not in data:
            logger.warning("MCP config has no 'servers' key")
            return

        for entry in data["servers"]:
            if not isinstance(entry, dict):
                logger.warning("Skipping non-dict MCP server entry")
                continue
            try:
                config = MCPServerConfig(**entry)
                self._servers[config.name] = config
                logger.info("Loaded MCP server config: %s (%s)", config.name, config.transport.value)
            except Exception as e:
                logger.warning("Skipping malformed MCP server entry: %s — %s", entry.get("name", "?"), e)

    def get_servers(self) -> dict[str, MCPServerConfig]:
        return dict(self._servers)

    def get(self, name: str) -> MCPServerConfig | None:
        return self._servers.get(name)

    @property
    def server_count(self) -> int:
        return len(self._servers)
