"""MCP tool registry: standardized tool calling for pipeline stages.

Separate from the MCP protocol client — this is the tool execution layer
that pipeline stages interact with.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0  # seconds (HB-01)


class ToolStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class ToolResult:
    """Result of a tool execution."""
    tool_name: str
    status: ToolStatus
    output: Any = None
    error: str = ""
    duration_ms: float = 0.0


@dataclass
class ToolDefinition:
    """Definition of an MCP tool."""
    name: str
    description: str
    handler: Callable[..., Awaitable[Any]]
    timeout: float = DEFAULT_TIMEOUT
    schema: dict = field(default_factory=dict)


class MCPToolRegistry:
    """Registry for MCP tools with safety guards.

    Tools are registered with handlers and optional timeouts.
    Calling a tool returns a ToolResult with status and output.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.debug("Registered MCP tool: %s", tool.name)

    async def call(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Call a registered tool by name."""
        if tool_name not in self._tools:
            return ToolResult(
                tool_name=tool_name,
                status=ToolStatus.ERROR,
                error=f"Unknown tool: {tool_name}",  # HB-02
            )

        tool = self._tools[tool_name]

        try:
            import time
            start = time.monotonic()

            result = await asyncio.wait_for(
                tool.handler(**kwargs),
                timeout=tool.timeout,  # HB-01
            )

            duration = (time.monotonic() - start) * 1000
            return ToolResult(
                tool_name=tool_name,
                status=ToolStatus.SUCCESS,
                output=result,
                duration_ms=duration,
            )

        except TimeoutError:
            return ToolResult(
                tool_name=tool_name,
                status=ToolStatus.TIMEOUT,
                error=f"Tool timed out after {tool.timeout}s",
            )
        except Exception as e:
            return ToolResult(
                tool_name=tool_name,
                status=ToolStatus.ERROR,
                error=str(e),
            )

    def list_tools(self) -> list[dict]:
        """List all registered tools with their schemas."""
        return [
            {"name": t.name, "description": t.description, "schema": t.schema}
            for t in self._tools.values()
        ]

    def has_tool(self, name: str) -> bool:
        return name in self._tools


# Built-in tool handlers

async def _search_handler(query: str = "", **kwargs) -> dict:
    """Built-in search tool (returns placeholder)."""
    return {"query": query, "results": [], "message": "Search tool placeholder"}


async def _code_exec_handler(code: str = "", language: str = "python", **kwargs) -> dict:
    """Built-in code execution tool (sandboxed placeholder)."""
    return {
        "code": code[:200],
        "language": language,
        "output": "",
        "message": "Code execution requires backend configuration",
    }


async def _file_read_handler(path: str = "", **kwargs) -> dict:
    """Built-in file read tool (with path restrictions)."""
    import os
    safe_path = os.path.normpath(path)
    if not safe_path.startswith("data") and not safe_path.startswith("./data"):
        return {"error": "Access denied: only data/ directory is readable"}
    try:
        with open(safe_path, encoding="utf-8") as f:
            content = f.read(10000)
        return {"content": content, "path": safe_path}
    except Exception as e:
        return {"error": str(e), "path": safe_path}


def create_default_registry() -> MCPToolRegistry:
    """Create registry with built-in tools."""
    registry = MCPToolRegistry()
    registry.register(ToolDefinition(
        name="search",
        description="Search for information on a topic",
        handler=_search_handler,
        schema={"query": {"type": "string", "required": True}},
    ))
    registry.register(ToolDefinition(
        name="code_exec",
        description="Execute code in a sandboxed environment",
        handler=_code_exec_handler,
        timeout=5.0,
        schema={"code": {"type": "string", "required": True}, "language": {"type": "string"}},
    ))
    registry.register(ToolDefinition(
        name="file_read",
        description="Read a file from the data/ directory",
        handler=_file_read_handler,
        schema={"path": {"type": "string", "required": True}},
    ))
    return registry
