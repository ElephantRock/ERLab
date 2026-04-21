"""Tests for subprocess sandbox backend."""

import os

import pytest

from backend.pipeline.sandboxing.protocol import SandboxConfig
from backend.pipeline.sandboxing.subprocess_backend import SubprocessSandboxBackend


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


class TestSubprocessBackend:
    def test_name(self):
        backend = SubprocessSandboxBackend()
        assert backend.name == "subprocess"

    def test_always_available(self):
        backend = SubprocessSandboxBackend()
        assert backend.is_available() is True

    @pytest.mark.anyio
    async def test_execute_shell(self):
        backend = SubprocessSandboxBackend()
        result = await backend.execute_shell("echo isolated")
        assert result.exit_code == 0
        assert "isolated" in result.stdout

    @pytest.mark.anyio
    async def test_execute_python(self):
        backend = SubprocessSandboxBackend()
        result = await backend.execute_python("print(2 + 2)")
        assert result.exit_code == 0
        assert "4" in result.stdout

    @pytest.mark.anyio
    async def test_environment_sanitized(self):
        """Uncommon env vars should not leak into the subprocess."""
        os.environ["_EROCK_TEST_LEAK"] = "should_not_appear"
        try:
            backend = SubprocessSandboxBackend()
            result = await backend.execute_python(
                "import os; print(os.environ.get('_EROCK_TEST_LEAK', 'NOT_FOUND'))"
            )
            assert "NOT_FOUND" in result.stdout
        finally:
            del os.environ["_EROCK_TEST_LEAK"]

    @pytest.mark.anyio
    async def test_environment_explicit(self):
        """Explicit env vars in config should be passed through."""
        cfg = SandboxConfig(environment={"_EROCK_TEST_PASS": "hello"})
        backend = SubprocessSandboxBackend(cfg)
        result = await backend.execute_python(
            "import os; print(os.environ.get('_EROCK_TEST_PASS', 'MISSING'))",
            config=cfg,
        )
        assert "hello" in result.stdout

    @pytest.mark.anyio
    async def test_command_allowlist_pass(self):
        cfg = SandboxConfig(allowed_commands=["echo"])
        backend = SubprocessSandboxBackend()
        result = await backend.execute_shell("echo allowed", config=cfg)
        assert result.exit_code == 0

    @pytest.mark.anyio
    async def test_command_allowlist_blocked(self):
        cfg = SandboxConfig(allowed_commands=["echo"])
        backend = SubprocessSandboxBackend()
        with pytest.raises(ValueError, match="not allowed"):
            await backend.execute_shell("python3 -c 'print(1)'", config=cfg)

    @pytest.mark.anyio
    async def test_timeout(self):
        cfg = SandboxConfig(timeout_seconds=0.5)
        backend = SubprocessSandboxBackend(cfg)
        result = await backend.execute_python("import time; time.sleep(5)")
        assert result.timed_out is True

    @pytest.mark.anyio
    async def test_output_truncation(self):
        cfg = SandboxConfig(max_output_bytes=15)
        backend = SubprocessSandboxBackend(cfg)
        result = await backend.execute_python("print('x' * 1000)")
        assert len(result.stdout.encode("utf-8")) <= 20

    @pytest.mark.anyio
    async def test_session(self):
        backend = SubprocessSandboxBackend()
        async with backend.create_session() as session:
            r1 = await session.execute_shell("echo first")
            assert "first" in r1.stdout
            r2 = await session.execute_python("print('second')")
            assert "second" in r2.stdout

    @pytest.mark.anyio
    async def test_working_directory(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = SandboxConfig(working_directory=tmpdir)
            backend = SubprocessSandboxBackend()
            result = await backend.execute_python(
                "import os; print(os.getcwd())", config=cfg,
            )
            assert tmpdir.replace("\\", "/") in result.stdout.replace("\\", "/")
