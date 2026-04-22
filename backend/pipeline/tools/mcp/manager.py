"""MCP manager — lifecycle coordinator for all MCP server connections."""

from __future__ import annotations

import logging
from typing import Any

from backend.pipeline.tools.mcp.adapter import MCPToolAdapter
from backend.pipeline.tools.mcp.client import MCPClient
from backend.pipeline.tools.mcp.models import MCPServerConfig, MCPTransport
from backend.pipeline.tools.mcp.server_registry import MCPServerRegistry

logger = logging.getLogger(__name__)


class MCPManager:
    """Owns all MCPClient instances, handles connect/disconnect lifecycle."""

    def __init__(
        self,
        server_registry: MCPServerRegistry,
        tool_registry: Any | None = None,
        tool_index: Any | None = None,
    ) -> None:
        self._server_registry = server_registry
        self._tool_registry = tool_registry
        self._tool_index = tool_index
        self._clients: dict[str, MCPClient] = {}
        self._started = False

    async def start(self) -> int:
        """Connect to all configured servers, discover and register tools.

        Returns number of tools registered.
        """
        if self._started:
            return 0

        total_tools = 0
        for name, config in self._server_registry.get_servers().items():
            try:
                client = await self._connect_server(config)
                self._clients[name] = client

                if self._tool_registry:
                    adapter = MCPToolAdapter(client, config)
                    tools = await adapter.discover_tools()
                    for tool_def in tools:
                        self._tool_registry.register(
                            name=tool_def.name,
                            handler=tool_def.handler,
                            description=tool_def.description,
                            parameters=tool_def.parameters,
                            timeout=tool_def.timeout,
                            trust_level=tool_def.trust_level,
                        )
                        if self._tool_index:
                            await self._tool_index.index_tool(tool_def)
                    total_tools += len(tools)
                    logger.info(
                        "MCP server '%s': discovered %d tools",
                        name, len(tools),
                    )
            except Exception as e:
                logger.error("Failed to connect MCP server '%s': %s", name, e)

        self._started = True
        logger.info("MCP manager started: %d servers, %d tools", len(self._clients), total_tools)
        return total_tools

    async def stop(self) -> None:
        """Gracefully disconnect all clients."""
        for name, client in self._clients.items():
            try:
                await client.disconnect()
            except Exception as e:
                logger.warning("Error disconnecting MCP client '%s': %s", name, e)
        self._clients.clear()
        self._started = False

    def health_check(self) -> dict[str, bool]:
        """Return per-server alive status."""
        return {name: client.is_alive() for name, client in self._clients.items()}

    async def _connect_server(self, config: MCPServerConfig) -> MCPClient:
        """Create a transport and client for a server config."""
        if config.transport == MCPTransport.STDIO:
            from backend.pipeline.tools.mcp.transport import StdIOTransport
            transport = StdIOTransport(
                command=config.command or "",
                args=config.args,
                env=config.env,
            )
        else:
            from backend.pipeline.tools.mcp.transport import HTTPTransport
            transport = HTTPTransport(
                url=config.url or "",
                timeout=config.timeout,
            )

        client = MCPClient(transport, name=config.name, timeout=config.timeout)
        await client.connect()
        return client
