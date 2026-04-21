"""Tests for SandboxManager — auto-detection, fallback, convenience API."""

import pytest

from backend.pipeline.sandboxing.manager import SandboxManager, reset_sandbox_manager
from backend.pipeline.sandboxing.protocol import SandboxConfig


@pytest.fixture(autouse=True)
def _reset():
    reset_sandbox_manager()
    yield
    reset_sandbox_manager()


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


class TestSandboxManager:
    def test_auto_detect_noop(self):
        """Auto-detect picks subprocess at minimum (both always available)."""
        mgr = SandboxManager(backend_name="auto")
        assert mgr.backend_name in ("docker", "subprocess", "noop")

    def test_explicit_noop(self):
        mgr = SandboxManager(backend_name="noop")
        assert mgr.backend_name == "noop"

    def test_explicit_subprocess(self):
        mgr = SandboxManager(backend_name="subprocess")
        assert mgr.backend_name == "subprocess"

    def test_explicit_docker_fallback(self):
        """If Docker requested but unavailable, falls back to noop."""
        mgr = SandboxManager(backend_name="docker")
        # May be docker or noop depending on environment
        assert mgr.backend_name in ("docker", "noop")

    def test_unknown_backend_fallback(self):
        mgr = SandboxManager(backend_name="nonexistent")
        assert mgr.backend_name == "noop"

    def test_list_backends(self):
        mgr = SandboxManager()
        backends = mgr.list_backends()
        assert "noop" in backends
        assert "subprocess" in backends
        assert "docker" in backends
        assert backends["noop"] is True
        assert backends["subprocess"] is True

    @pytest.mark.anyio
    async def test_execute_shell(self):
        mgr = SandboxManager(backend_name="noop")
        result = await mgr.execute_shell("echo manager_test")
        assert result.exit_code == 0
        assert "manager_test" in result.stdout

    @pytest.mark.anyio
    async def test_execute_python(self):
        mgr = SandboxManager(backend_name="noop")
        result = await mgr.execute_python("print(99)")
        assert "99" in result.stdout

    @pytest.mark.anyio
    async def test_session(self):
        mgr = SandboxManager(backend_name="subprocess")
        async with mgr.create_session() as session:
            result = await session.execute_shell("echo session_ok")
            assert "session_ok" in result.stdout

    def test_default_config_propagated(self):
        cfg = SandboxConfig(timeout_seconds=5.0, memory_limit_mb=128)
        mgr = SandboxManager(backend_name="noop", default_config=cfg)
        # The noop backend should have received the config
        assert mgr._backends["noop"]._default_config.timeout_seconds == 5.0

    def test_get_backend(self):
        mgr = SandboxManager()
        noop = mgr.get_backend("noop")
        assert noop is not None
        assert noop.name == "noop"
        assert mgr.get_backend("nonexistent") is None

    @pytest.mark.anyio
    async def test_subprocess_execution(self):
        mgr = SandboxManager(backend_name="subprocess")
        result = await mgr.execute_python("print('subprocess works')")
        assert "subprocess works" in result.stdout
