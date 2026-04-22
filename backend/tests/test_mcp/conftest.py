"""Shared fixtures for MCP tests."""

import pytest

from backend.pipeline.tools.mcp.models import MCPServerConfig, MCPTransport


@pytest.fixture
def stdio_config() -> MCPServerConfig:
    return MCPServerConfig(
        name="test-server",
        transport=MCPTransport.STDIO,
        command="echo",
        args=["hello"],
        timeout=5.0,
    )


@pytest.fixture
def http_config() -> MCPServerConfig:
    return MCPServerConfig(
        name="test-http",
        transport=MCPTransport.HTTP_SSE,
        url="http://localhost:9999/mcp",
        timeout=10.0,
    )
