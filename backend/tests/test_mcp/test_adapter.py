"""Tests for MCP tool adapter — schema translation and ToolDefinition creation."""

import pytest

from backend.pipeline.tools.mcp.adapter import MCPToolAdapter, _translate_schema
from backend.pipeline.tools.mcp.models import MCPServerConfig, MCPTransport
from backend.tests.test_mcp.test_client import FakeTransport

from backend.pipeline.tools.mcp.client import MCPClient

import pytest
pytestmark = pytest.mark.flaky(reruns=2, reruns_delay=1)


@pytest.fixture
def fake_client():
    transport = FakeTransport()
    transport._connected = True
    return MCPClient(transport, name="test")


@pytest.fixture
def server_config():
    return MCPServerConfig(
        name="test-server",
        transport=MCPTransport.STDIO,
        command="echo",
        timeout=10.0,
        trust_level="untrusted",
    )


class TestSchemaTranslation:
    def test_basic_properties(self):
        schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        }
        result = _translate_schema(schema)
        assert "query" in result
        assert result["query"]["required"] is True
        assert result["query"]["type"] == "string"
        assert result["limit"]["type"] == "integer"
        assert result["limit"]["default"] == 10

    def test_empty_schema(self):
        result = _translate_schema({})
        assert result == {}

    def test_no_required(self):
        schema = {
            "properties": {"q": {"type": "string"}},
        }
        result = _translate_schema(schema)
        assert "required" not in result.get("q", {})


class TestMCPToolAdapterDiscover:
    @pytest.mark.anyio
    async def test_discovers_tools(self, fake_client, server_config):
        fake_client._transport.set_response("tools/list", {
            "tools": [
                {"name": "search", "description": "Search items", "inputSchema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                }},
            ]
        })
        adapter = MCPToolAdapter(fake_client, server_config)
        tools = await adapter.discover_tools()
        assert len(tools) == 1
        assert tools[0].name == "mcp__test-server__search"
        assert tools[0].source == "mcp"
        assert tools[0].trust_level == "untrusted"

    @pytest.mark.anyio
    async def test_namespacing(self, fake_client, server_config):
        fake_client._transport.set_response("tools/list", {
            "tools": [
                {"name": "get", "description": "Get", "inputSchema": {}},
            ]
        })
        adapter = MCPToolAdapter(fake_client, server_config)
        tools = await adapter.discover_tools()
        assert tools[0].name.startswith("mcp__test-server__")

    @pytest.mark.anyio
    async def test_empty_server(self, fake_client, server_config):
        fake_client._transport.set_response("tools/list", {"tools": []})
        adapter = MCPToolAdapter(fake_client, server_config)
        tools = await adapter.discover_tools()
        assert tools == []

    @pytest.mark.anyio
    async def test_handler_is_callable(self, fake_client, server_config):
        fake_client._transport.set_response("tools/list", {
            "tools": [
                {"name": "echo", "description": "Echo", "inputSchema": {}},
            ]
        })
        adapter = MCPToolAdapter(fake_client, server_config)
        tools = await adapter.discover_tools()
        assert callable(tools[0].handler)

    @pytest.mark.anyio
    async def test_handler_calls_mcp(self, fake_client, server_config):
        fake_client._transport.set_response("tools/list", {
            "tools": [{"name": "echo", "description": "Echo", "inputSchema": {}}],
        })
        fake_client._transport.set_response("tools/call", {
            "content": [{"type": "text", "text": "hello world"}],
            "isError": False,
        })
        adapter = MCPToolAdapter(fake_client, server_config)
        tools = await adapter.discover_tools()
        result = await tools[0].handler()
        assert result == "hello world"

    @pytest.mark.anyio
    async def test_schema_translation_in_discovery(self, fake_client, server_config):
        fake_client._transport.set_response("tools/list", {
            "tools": [{
                "name": "search",
                "description": "Search",
                "inputSchema": {
                    "type": "object",
                    "properties": {"q": {"type": "string"}},
                    "required": ["q"],
                },
            }],
        })
        adapter = MCPToolAdapter(fake_client, server_config)
        tools = await adapter.discover_tools()
        assert tools[0].parameters["q"]["required"] is True

    @pytest.mark.anyio
    async def test_register_all_raises(self, fake_client, server_config):
        adapter = MCPToolAdapter(fake_client, server_config)
        with pytest.raises(NotImplementedError):
            adapter.register_all(None)

    @pytest.mark.anyio
    async def test_multiple_tools(self, fake_client, server_config):
        fake_client._transport.set_response("tools/list", {
            "tools": [
                {"name": "a", "description": "Tool A", "inputSchema": {}},
                {"name": "b", "description": "Tool B", "inputSchema": {}},
                {"name": "c", "description": "Tool C", "inputSchema": {}},
            ]
        })
        adapter = MCPToolAdapter(fake_client, server_config)
        tools = await adapter.discover_tools()
        assert len(tools) == 3
        names = {t.name for t in tools}
        assert names == {"mcp__test-server__a", "mcp__test-server__b", "mcp__test-server__c"}
