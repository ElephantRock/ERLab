"""MCP integration — Model Context Protocol client, transport, and tool adapter."""

from backend.pipeline.tools.mcp.adapter import MCPToolAdapter
from backend.pipeline.tools.mcp.client import MCPClient
from backend.pipeline.tools.mcp.manager import MCPManager
from backend.pipeline.tools.mcp.models import (
    MCPCallResult,
    MCPContentBlock,
    MCPServerConfig,
    MCPToolInfo,
    MCPTransport,
)
from backend.pipeline.tools.mcp.server_registry import MCPServerRegistry

__all__ = [
    "MCPClient",
    "MCPManager",
    "MCPServerConfig",
    "MCPServerRegistry",
    "MCPToolAdapter",
    "MCPToolInfo",
    "MCPTransport",
    "MCPCallResult",
    "MCPContentBlock",
]
