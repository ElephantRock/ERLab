"""MCP data models — server configs, tool info, call results."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MCPTransport(str, Enum):
    STDIO = "stdio"
    HTTP_SSE = "http_sse"


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server connection."""

    name: str
    transport: MCPTransport = MCPTransport.STDIO
    command: str | None = None  # For stdio transport
    url: str | None = None  # For http_sse transport
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    timeout: float = 30.0
    trust_level: str = "untrusted"  # "trusted" or "untrusted"


class MCPToolInfo(BaseModel):
    """Tool metadata returned by an MCP server's list_tools."""

    name: str
    description: str = ""
    inputSchema: dict[str, Any] = Field(default_factory=dict)


class MCPContentBlock(BaseModel):
    """A single content block in an MCP call result."""

    type: str = "text"
    text: str = ""


class MCPCallResult(BaseModel):
    """Result from calling an MCP tool."""

    content: list[MCPContentBlock] = Field(default_factory=list)
    isError: bool = False

    @property
    def text(self) -> str:
        """Concatenate all text blocks."""
        return "\n".join(b.text for b in self.content if b.type == "text")
