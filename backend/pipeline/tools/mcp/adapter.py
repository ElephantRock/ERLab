"""MCP tool adapter — bridges MCP tools to the existing ToolRegistry."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.pipeline.tools.mcp.client import MCPClient
from backend.pipeline.tools.mcp.models import MCPServerConfig
from backend.pipeline.tools.registry import ToolDefinition

logger = logging.getLogger(__name__)


def _translate_schema(mcp_schema: dict[str, Any]) -> dict[str, Any]:
    """Convert MCP JSON Schema properties to ToolRegistry parameter dict format."""
    properties = mcp_schema.get("properties", {})
    required = set(mcp_schema.get("required", []))

    params: dict[str, Any] = {}
    for name, prop in properties.items():
        param: dict[str, Any] = {"type": prop.get("type", "string")}
        if name in required:
            param["required"] = True
        if "description" in prop:
            param["description"] = prop["description"]
        if "default" in prop:
            param["default"] = prop["default"]
        params[name] = param

    return params


class MCPToolAdapter:
    """Discovers MCP tools and wraps them as ToolDefinitions."""

    def __init__(self, client: MCPClient, config: MCPServerConfig) -> None:
        self._client = client
        self._config = config

    async def discover_tools(self) -> list[ToolDefinition]:
        """List tools from the MCP server and wrap each as a ToolDefinition."""
        tools_info = await self._client.list_tools()
        definitions = []
        for info in tools_info:
            prefixed_name = f"mcp__{self._config.name}__{info.name}"
            params = _translate_schema(info.inputSchema)
            handler = self._make_handler(info.name)
            defn = ToolDefinition(
                name=prefixed_name,
                description=info.description,
                parameters=params,
                handler=handler,
                timeout=self._config.timeout,
                trust_level=self._config.trust_level,
                source="mcp",
            )
            definitions.append(defn)
        return definitions

    def register_all(self, registry: Any) -> int:
        """Discover and register all tools. Returns count registered."""
        # This must be called from an async context — the caller should
        # use the result of discover_tools() and register manually.
        # Kept for convenience in async contexts.
        raise NotImplementedError("Use discover_tools() + registry.register() in async context")

    def _make_handler(self, tool_name: str):
        """Create an async handler that calls the MCP tool."""
        client = self._client
        config = self._config

        async def handler(**kwargs: Any) -> str:
            result = await asyncio.wait_for(
                client.call_tool(tool_name, arguments=kwargs),
                timeout=config.timeout,
            )
            if result.isError:
                raise RuntimeError(f"MCP tool '{tool_name}' returned error: {result.text}")
            return result.text

        return handler
