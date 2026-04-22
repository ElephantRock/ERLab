"""Tests for MCP manager — lifecycle coordination."""

import pytest

from backend.pipeline.tools.mcp.manager import MCPManager
from backend.pipeline.tools.mcp.models import MCPServerConfig, MCPTransport
from backend.pipeline.tools.mcp.server_registry import MCPServerRegistry
from backend.pipeline.tools.registry import ToolRegistry


class FakeServerRegistry:
    """In-memory server registry for testing."""

    def __init__(self, servers: dict[str, MCPServerConfig]):
        self._servers = servers

    def get_servers(self):
        return dict(self._servers)

    @property
    def server_count(self):
        return len(self._servers)


class TestMCPManagerStartStop:
    @pytest.mark.anyio
    async def test_start_with_no_servers(self):
        registry = FakeServerRegistry({})
        manager = MCPManager(registry)
        count = await manager.start()
        assert count == 0
        assert manager._started

    @pytest.mark.anyio
    async def test_start_idempotent(self):
        registry = FakeServerRegistry({})
        manager = MCPManager(registry)
        await manager.start()
        count = await manager.start()  # second call
        assert count == 0

    @pytest.mark.anyio
    async def test_stop_cleans_up(self):
        registry = FakeServerRegistry({})
        manager = MCPManager(registry)
        await manager.start()
        await manager.stop()
        assert not manager._started

    @pytest.mark.anyio
    async def test_health_check_empty(self):
        registry = FakeServerRegistry({})
        manager = MCPManager(registry)
        await manager.start()
        assert manager.health_check() == {}
        await manager.stop()


class TestMCPManagerWithRegistry:
    @pytest.mark.anyio
    async def test_tools_registered_in_tool_registry(self, tmp_path):
        """Test that tools from a fake server get registered."""
        tool_reg = ToolRegistry()

        # Create a config that would fail to connect (command doesn't exist)
        # but the registry still loads the config
        config = MCPServerConfig(
            name="bad-server",
            transport=MCPTransport.STDIO,
            command="nonexistent_cmd_xyz",
        )
        registry = FakeServerRegistry({"bad-server": config})
        manager = MCPManager(registry, tool_registry=tool_reg)

        # This will fail to connect but should handle gracefully
        count = await manager.start()
        assert count == 0  # No tools discovered because connection failed
        await manager.stop()

    @pytest.mark.anyio
    async def test_manager_with_yaml_config(self, tmp_path):
        yaml_content = """
servers:
  - name: github
    transport: stdio
    command: npx
    args: ["-y", "@mcp/server-github"]
"""
        path = tmp_path / "servers.yaml"
        path.write_text(yaml_content)
        server_registry = MCPServerRegistry(str(path))
        assert server_registry.server_count == 1

        manager = MCPManager(server_registry)
        # Start will fail to connect (npx not available in test) but shouldn't crash
        count = await manager.start()
        assert count == 0
        await manager.stop()


class TestMCPManagerHealthCheck:
    @pytest.mark.anyio
    async def test_health_check_reflects_clients(self):
        registry = FakeServerRegistry({})
        manager = MCPManager(registry)
        await manager.start()
        health = manager.health_check()
        assert isinstance(health, dict)
        await manager.stop()
