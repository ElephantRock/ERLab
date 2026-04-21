"""Tests for Docker sandbox backend — marked integration (requires Docker)."""

import pytest

from backend.pipeline.sandboxing.docker_backend import DockerSandboxBackend
from backend.pipeline.sandboxing.protocol import SandboxConfig


pytestmark = pytest.mark.integration

@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


class TestDockerBackend:
    def test_name(self):
        backend = DockerSandboxBackend()
        assert backend.name == "docker"

    @pytest.mark.anyio
    async def test_execute_shell(self):
        backend = DockerSandboxBackend()
        if not await backend.check_available_async():
            pytest.skip("Docker not available")
        result = await backend.execute_shell("echo docker_works")
        assert result.exit_code == 0
        assert "docker_works" in result.stdout

    @pytest.mark.anyio
    async def test_execute_python(self):
        backend = DockerSandboxBackend()
        if not await backend.check_available_async():
            pytest.skip("Docker not available")
        result = await backend.execute_python("print(6 * 7)")
        assert result.exit_code == 0
        assert "42" in result.stdout

    @pytest.mark.anyio
    async def test_network_disabled(self):
        cfg = SandboxConfig(network_enabled=False)
        backend = DockerSandboxBackend()
        if not await backend.check_available_async():
            pytest.skip("Docker not available")
        result = await backend.execute_shell(
            "ping -c 1 8.8.8.8 2>&1 || echo network_blocked",
            config=cfg,
        )
        # Should fail since network is disabled
        assert "network_blocked" in result.stdout or result.exit_code != 0

    @pytest.mark.anyio
    async def test_timeout(self):
        cfg = SandboxConfig(timeout_seconds=1.0)
        backend = DockerSandboxBackend()
        if not await backend.check_available_async():
            pytest.skip("Docker not available")
        result = await backend.execute_shell("sleep 30", config=cfg)
        assert result.timed_out is True

    @pytest.mark.anyio
    async def test_session(self):
        backend = DockerSandboxBackend()
        if not await backend.check_available_async():
            pytest.skip("Docker not available")
        async with await backend.create_session() as session:
            r1 = await session.execute_shell("echo first")
            assert "first" in r1.stdout
            r2 = await session.execute_python("print('second')")
            assert "second" in r2.stdout
