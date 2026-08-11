"""Tests for MCP transports — StdIO and HTTP."""

import json

import pytest

from backend.pipeline.tools.mcp.transport import BaseTransport, HTTPTransport, StdIOTransport


class TestBaseTransport:
    def test_is_abstract(self):
        assert BaseTransport.__abstractmethods__


class TestStdIOTransport:
    @pytest.mark.anyio
    async def test_connect_and_is_connected(self):
        transport = StdIOTransport(command="cat")
        await transport.connect()
        assert transport.is_connected
        await transport.disconnect()

    @pytest.mark.anyio
    async def test_disconnect_cleans_up(self):
        transport = StdIOTransport(command="cat")
        await transport.connect()
        await transport.disconnect()
        assert not transport.is_connected

    @pytest.mark.anyio
    async def test_send_request_echo(self):
        """Use `cat` as a subprocess that echoes stdin back to stdout."""
        transport = StdIOTransport(command="cat")
        await transport.connect()

        request = {"jsonrpc": "2.0", "id": 1, "method": "test"}
        line = json.dumps(request) + "\n"
        transport._process.stdin.write(line.encode())
        await transport._process.stdin.drain()

        response_line = await transport._process.stdout.readline()
        data = json.loads(response_line.decode().strip())
        assert data["method"] == "test"

        await transport.disconnect()

    @pytest.mark.anyio
    async def test_request_id_increments(self):
        transport = StdIOTransport(command="cat")
        id1 = transport._next_id()
        id2 = transport._next_id()
        assert id2 == id1 + 1

    @pytest.mark.anyio
    async def test_send_request_when_not_connected(self):
        transport = StdIOTransport(command="cat")
        with pytest.raises(ConnectionError, match="not running"):
            await transport.send_request("test")

    @pytest.mark.anyio
    async def test_connect_invalid_command(self):
        transport = StdIOTransport(command="nonexistent_command_xyz")
        with pytest.raises(FileNotFoundError):
            await transport.connect()

    @pytest.mark.anyio
    async def test_disconnect_idempotent(self):
        transport = StdIOTransport(command="cat")
        await transport.connect()
        await transport.disconnect()
        await transport.disconnect()  # should not raise


class TestHTTPTransport:
    def test_initial_state(self):
        transport = HTTPTransport(url="http://localhost:9999/mcp")
        assert not transport.is_connected

    @pytest.mark.anyio
    async def test_connect_sets_connected(self):
        transport = HTTPTransport(url="http://localhost:9999/mcp")
        try:
            await transport.connect()
            assert transport.is_connected
        except ImportError:
            pytest.skip("httpx not installed")
        finally:
            await transport.disconnect()

    @pytest.mark.anyio
    async def test_disconnect_clears_connected(self):
        transport = HTTPTransport(url="http://localhost:9999/mcp")
        try:
            await transport.connect()
        except ImportError:
            pytest.skip("httpx not installed")
        await transport.disconnect()
        assert not transport.is_connected

    @pytest.mark.anyio
    async def test_send_request_when_not_connected(self):
        transport = HTTPTransport(url="http://localhost:9999/mcp")
        with pytest.raises(ConnectionError, match="not initialized"):
            await transport.send_request("test")

    def test_timeout_stored(self):
        transport = HTTPTransport(url="http://localhost:9999/mcp", timeout=60.0)
        assert transport._timeout == 60.0
