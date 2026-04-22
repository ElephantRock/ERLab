"""Tests for MCP server registry — YAML loading and validation."""

import pytest

from backend.pipeline.tools.mcp.models import MCPTransport
from backend.pipeline.tools.mcp.server_registry import MCPServerRegistry


class TestMCPServerRegistryMissingFile:
    def test_missing_file_no_error(self, tmp_path):
        registry = MCPServerRegistry(str(tmp_path / "nonexistent.yaml"))
        assert registry.server_count == 0

    def test_missing_file_empty_servers(self, tmp_path):
        registry = MCPServerRegistry(str(tmp_path / "nonexistent.yaml"))
        assert registry.get_servers() == {}


class TestMCPServerRegistryValidYaml:
    def test_loads_single_server(self, tmp_path):
        yaml_content = """
servers:
  - name: github
    transport: stdio
    command: npx
    args: ["-y", "@mcp/server-github"]
    timeout: 60.0
    trust_level: untrusted
"""
        path = tmp_path / "servers.yaml"
        path.write_text(yaml_content)
        registry = MCPServerRegistry(str(path))
        assert registry.server_count == 1

        config = registry.get("github")
        assert config is not None
        assert config.transport == MCPTransport.STDIO
        assert config.command == "npx"
        assert config.timeout == 60.0

    def test_loads_multiple_servers(self, tmp_path):
        yaml_content = """
servers:
  - name: server-a
    transport: stdio
    command: npx
    args: ["-y", "pkg-a"]
  - name: server-b
    transport: http_sse
    url: http://localhost:3001/sse
"""
        path = tmp_path / "servers.yaml"
        path.write_text(yaml_content)
        registry = MCPServerRegistry(str(path))
        assert registry.server_count == 2
        assert registry.get("server-a").transport == MCPTransport.STDIO
        assert registry.get("server-b").transport == MCPTransport.HTTP_SSE


class TestMCPServerRegistryMalformed:
    def test_skips_malformed_entry(self, tmp_path):
        yaml_content = """
servers:
  - name: valid
    command: npx
  - not_a_dict: true
"""
        path = tmp_path / "servers.yaml"
        path.write_text(yaml_content)
        registry = MCPServerRegistry(str(path))
        assert registry.server_count == 1

    def test_empty_yaml(self, tmp_path):
        path = tmp_path / "servers.yaml"
        path.write_text("")
        registry = MCPServerRegistry(str(path))
        assert registry.server_count == 0

    def test_no_servers_key(self, tmp_path):
        path = tmp_path / "servers.yaml"
        path.write_text("other_key: value\n")
        registry = MCPServerRegistry(str(path))
        assert registry.server_count == 0

    def test_get_nonexistent(self, tmp_path):
        registry = MCPServerRegistry(str(tmp_path / "missing.yaml"))
        assert registry.get("nonexistent") is None
