"""Tests for MCP client."""

import asyncio
import json

import pytest

from backend.pipeline.tools.mcp.client import MCPClient
from backend.pipeline.tools.mcp.models import MCPCallResult, MCPContentBlock, MCPToolInfo


class FakeTransport:
    """In-memory transport that echoes JSON-RPC responses."""

    def __init__(self):
        self._connected = False
        self._request_counter = 0
        self._responses: dict[str, dict] = {}

    def set_response(self, method: str, result: dict):
        self._responses[method] = result

    async def connect(self):
        self._connected = True

    async def disconnect(self):
        self._connected = False

    async def send_request(self, method: str, params=None):
        if method in self._responses:
            return self._responses[method]
        # Default: empty result
        return {}

    @property
    def is_connected(self):
        return self._connected


@pytest.fixture
def fake_transport():
    return FakeTransport()


@pytest.fixture
def client(fake_transport):
    return MCPClient(fake_transport, name="test-server", timeout=5.0)


class TestMCPClientLifecycle:
    @pytest.mark.anyio
    async def test_connect(self, client, fake_transport):
        await client.connect()
        assert fake_transport.is_connected

    @pytest.mark.anyio
    async def test_disconnect(self, client, fake_transport):
        await client.connect()
        await client.disconnect()
        assert not fake_transport.is_connected

    @pytest.mark.anyio
    async def test_is_alive(self, client, fake_transport):
        assert not client.is_alive()
        await client.connect()
        assert client.is_alive()
        await client.disconnect()
        assert not client.is_alive()

    @pytest.mark.anyio
    async def test_name_property(self, client):
        assert client.name == "test-server"


class TestMCPClientListTools:
    @pytest.mark.anyio
    async def test_list_tools(self, client, fake_transport):
        fake_transport.set_response("tools/list", {
            "tools": [
                {"name": "search", "description": "Search items", "inputSchema": {"type": "object"}},
                {"name": "get", "description": "Get item", "inputSchema": {"type": "object"}},
            ]
        })
        await client.connect()
        tools = await client.list_tools()
        assert len(tools) == 2
        assert tools[0].name == "search"
        assert tools[1].name == "get"

    @pytest.mark.anyio
    async def test_list_tools_empty(self, client, fake_transport):
        fake_transport.set_response("tools/list", {"tools": []})
        await client.connect()
        tools = await client.list_tools()
        assert tools == []


class TestMCPClientCallTool:
    @pytest.mark.anyio
    async def test_call_tool(self, client, fake_transport):
        fake_transport.set_response("tools/call", {
            "content": [{"type": "text", "text": "result text"}],
            "isError": False,
        })
        await client.connect()
        result = await client.call_tool("search", {"query": "test"})
        assert result.text == "result text"
        assert not result.isError

    @pytest.mark.anyio
    async def test_call_tool_error(self, client, fake_transport):
        fake_transport.set_response("tools/call", {
            "content": [{"type": "text", "text": "error occurred"}],
            "isError": True,
        })
        await client.connect()
        result = await client.call_tool("bad_tool")
        assert result.isError
        assert "error" in result.text
