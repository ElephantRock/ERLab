"""Tests for MCP data models."""

import pytest

from backend.pipeline.tools.mcp.models import (
    MCPCallResult,
    MCPContentBlock,
    MCPServerConfig,
    MCPToolInfo,
    MCPTransport,
)


class TestMCPTransport:
    def test_values(self):
        assert MCPTransport.STDIO.value == "stdio"
        assert MCPTransport.HTTP_SSE.value == "http_sse"


class TestMCPServerConfig:
    def test_stdio_config(self):
        config = MCPServerConfig(
            name="test",
            transport=MCPTransport.STDIO,
            command="npx",
            args=["-y", "@mcp/server"],
        )
        assert config.name == "test"
        assert config.transport == MCPTransport.STDIO
        assert config.command == "npx"
        assert config.args == ["-y", "@mcp/server"]
        assert config.timeout == 30.0
        assert config.trust_level == "untrusted"

    def test_http_config(self):
        config = MCPServerConfig(
            name="remote",
            transport=MCPTransport.HTTP_SSE,
            url="http://localhost:3001/sse",
            timeout=60.0,
            trust_level="trusted",
        )
        assert config.url == "http://localhost:3001/sse"
        assert config.timeout == 60.0
        assert config.trust_level == "trusted"

    def test_env_dict(self):
        config = MCPServerConfig(
            name="gh",
            command="npx",
            env={"GITHUB_TOKEN": "abc123"},
        )
        assert config.env["GITHUB_TOKEN"] == "abc123"

    def test_defaults(self):
        config = MCPServerConfig(name="minimal")
        assert config.command is None
        assert config.url is None
        assert config.args == []
        assert config.env == {}


class TestMCPToolInfo:
    def test_basic(self):
        info = MCPToolInfo(name="search", description="Search for items")
        assert info.name == "search"
        assert info.inputSchema == {}

    def test_with_schema(self):
        info = MCPToolInfo(
            name="search",
            description="Search",
            inputSchema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        )
        assert "query" in info.inputSchema["properties"]


class TestMCPCallResult:
    def test_text_property(self):
        result = MCPCallResult(content=[
            MCPContentBlock(type="text", text="hello"),
            MCPContentBlock(type="text", text="world"),
        ])
        assert result.text == "hello\nworld"

    def test_empty_content(self):
        result = MCPCallResult()
        assert result.text == ""
        assert result.isError is False

    def test_error_result(self):
        result = MCPCallResult(
            content=[MCPContentBlock(text="something went wrong")],
            isError=True,
        )
        assert result.isError is True
        assert "wrong" in result.text

    def test_mixed_content(self):
        result = MCPCallResult(content=[
            MCPContentBlock(type="text", text="ok"),
            MCPContentBlock(type="image", text=""),
        ])
        assert result.text == "ok"
