"""MCP client — wraps a transport, provides list_tools and call_tool."""

from __future__ import annotations

import asyncio
import logging

from backend.pipeline.tools.mcp.models import MCPCallResult, MCPContentBlock, MCPToolInfo
from backend.pipeline.tools.mcp.transport import BaseTransport

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 1.0


class MCPClient:
    """Client for a single MCP server."""

    def __init__(self, transport: BaseTransport, name: str = "", timeout: float = 30.0) -> None:
        self._transport = transport
        self._name = name
        self._timeout = timeout

    async def connect(self) -> None:
        """Connect with retry and exponential backoff."""
        for attempt in range(MAX_RETRIES):
            try:
                await asyncio.wait_for(self._transport.connect(), timeout=self._timeout)
                logger.info("MCP client '%s' connected", self._name)
                return
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    delay = BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "MCP client '%s' connect failed (attempt %d/%d): %s — retrying in %.1fs",
                        self._name, attempt + 1, MAX_RETRIES, e, delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise

    async def disconnect(self) -> None:
        await self._transport.disconnect()
        logger.info("MCP client '%s' disconnected", self._name)

    async def list_tools(self) -> list[MCPToolInfo]:
        """List available tools from the MCP server."""
        result = await asyncio.wait_for(
            self._transport.send_request("tools/list"),
            timeout=self._timeout,
        )
        tools = []
        for tool_data in result.get("tools", []):
            tools.append(MCPToolInfo(
                name=tool_data.get("name", ""),
                description=tool_data.get("description", ""),
                inputSchema=tool_data.get("inputSchema", {}),
            ))
        return tools

    async def call_tool(self, name: str, arguments: dict | None = None) -> MCPCallResult:
        """Call a tool on the MCP server."""
        params: dict = {"name": name}
        if arguments:
            params["arguments"] = arguments

        result = await asyncio.wait_for(
            self._transport.send_request("tools/call", params),
            timeout=self._timeout,
        )

        content: list[MCPContentBlock] = []
        for block in result.get("content", []):
            content.append(MCPContentBlock(
                type=block.get("type", "text"),
                text=block.get("text", ""),
            ))

        return MCPCallResult(
            content=content,
            isError=result.get("isError", False),
        )

    def is_alive(self) -> bool:
        return self._transport.is_connected

    @property
    def name(self) -> str:
        return self._name
