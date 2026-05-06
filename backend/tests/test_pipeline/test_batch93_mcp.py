"""Tests for BATCH-93 — MCP Tool Integration.

AIV v5.3 — T1, T2, T5. Use asyncio.run() not @pytest.mark.asyncio.
"""
from __future__ import annotations

import asyncio
import pytest

from backend.pipeline.tools.tool_registry import (
    MCPToolRegistry, ToolDefinition, ToolResult, ToolStatus,
    create_default_registry,
)


async def _echo_handler(message: str = "hello", **kwargs) -> str:
    return f"Echo: {message}"


async def _slow_handler(**kwargs):
    await asyncio.sleep(100)
    return "never"


async def _failing_handler(**kwargs):
    raise ValueError("Tool crashed!")


def test_93_01_register_and_list():
    """Can register and list tools."""
    registry = MCPToolRegistry()
    registry.register(ToolDefinition(name="echo", description="Echo tool", handler=_echo_handler))
    tools = registry.list_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "echo"


def test_93_01_call_tool_success():
    """Calling a registered tool returns success."""
    registry = MCPToolRegistry()
    registry.register(ToolDefinition(name="echo", description="Echo", handler=_echo_handler))
    result = asyncio.run(registry.call("echo", message="test"))
    assert result.status == ToolStatus.SUCCESS
    assert "test" in result.output


def test_93_02_unknown_tool_returns_error():
    """Unknown tool returns error, doesn't crash (HB-02)."""
    registry = MCPToolRegistry()
    result = asyncio.run(registry.call("nonexistent"))
    assert result.status == ToolStatus.ERROR
    assert "Unknown tool" in result.error


def test_93_02_tool_failure_isolated():
    """Tool failure doesn't crash registry (BAC-02)."""
    registry = MCPToolRegistry()
    registry.register(ToolDefinition(name="fail", description="Fails", handler=_failing_handler))
    result = asyncio.run(registry.call("fail"))
    assert result.status == ToolStatus.ERROR
    assert "Tool crashed" in result.error


def test_93_02_timeout_enforced():
    """Tool timeout is enforced (HB-01)."""
    registry = MCPToolRegistry()
    registry.register(ToolDefinition(name="slow", description="Slow", handler=_slow_handler, timeout=0.1))
    result = asyncio.run(registry.call("slow"))
    assert result.status == ToolStatus.TIMEOUT


def test_93_03_default_registry_has_tools():
    """Default registry has built-in tools."""
    registry = create_default_registry()
    assert registry.has_tool("search")
    assert registry.has_tool("code_exec")
    assert registry.has_tool("file_read")


def test_93_03_search_tool_returns_result():
    """Search tool returns placeholder results."""
    registry = create_default_registry()
    result = asyncio.run(registry.call("search", query="test"))
    assert result.status == ToolStatus.SUCCESS
    assert "query" in result.output


def test_93_03_has_tool():
    """has_tool checks registration."""
    registry = MCPToolRegistry()
    assert registry.has_tool("nothing") is False
    registry.register(ToolDefinition(name="test", description="T", handler=_echo_handler))
    assert registry.has_tool("test") is True
