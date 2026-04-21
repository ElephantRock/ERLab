"""Tests for noop sandbox backend."""

import asyncio

import pytest

from backend.pipeline.sandboxing.noop_backend import NoopSandboxBackend
from backend.pipeline.sandboxing.protocol import SandboxConfig


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


class TestNoopBackend:
    def test_name(self):
        backend = NoopSandboxBackend()
        assert backend.name == "noop"

    def test_always_available(self):
        backend = NoopSandboxBackend()
        assert backend.is_available() is True

    @pytest.mark.anyio
    async def test_execute_shell(self):
        backend = NoopSandboxBackend()
        result = await backend.execute_shell("echo hello")
        assert result.exit_code == 0
        assert "hello" in result.stdout
        assert result.timed_out is False

    @pytest.mark.anyio
    async def test_execute_python(self):
        backend = NoopSandboxBackend()
        result = await backend.execute_python("print(42)")
        assert result.exit_code == 0
        assert "42" in result.stdout

    @pytest.mark.anyio
    async def test_timeout(self):
        cfg = SandboxConfig(timeout_seconds=0.5)
        backend = NoopSandboxBackend(cfg)
        # On Windows, use timeout command or python sleep
        result = await backend.execute_python("import time; time.sleep(5)")
        assert result.timed_out is True

    @pytest.mark.anyio
    async def test_output_truncation(self):
        cfg = SandboxConfig(max_output_bytes=20)
        backend = NoopSandboxBackend(cfg)
        result = await backend.execute_python("print('x' * 1000)")
        assert len(result.stdout.encode("utf-8")) <= 25  # Allow small overhead

    @pytest.mark.anyio
    async def test_session_context_manager(self):
        backend = NoopSandboxBackend()
        session = backend.create_session()
        async with session:
            result = await session.execute_shell("echo session")
            assert result.exit_code == 0
            assert "session" in result.stdout

    @pytest.mark.anyio
    async def test_session_python(self):
        backend = NoopSandboxBackend()
        async with backend.create_session() as session:
            result = await session.execute_python("print('from session')")
            assert "from session" in result.stdout

    @pytest.mark.anyio
    async def test_failed_command(self):
        backend = NoopSandboxBackend()
        result = await backend.execute_shell("exit 1")
        assert result.exit_code != 0

    @pytest.mark.anyio
    async def test_stderr_captured(self):
        backend = NoopSandboxBackend()
        result = await backend.execute_python("import sys; print('err', file=sys.stderr)")
        assert "err" in result.stderr
