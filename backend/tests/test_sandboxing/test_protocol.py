"""Tests for sandbox protocol types and config validation."""

from backend.pipeline.sandboxing.protocol import (
    ExecutionResult,
    SandboxConfig,
    SandboxSession,
)


class TestSandboxConfig:
    def test_defaults(self):
        cfg = SandboxConfig()
        assert cfg.timeout_seconds == 30.0
        assert cfg.max_output_bytes == 100_000
        assert cfg.memory_limit_mb == 256
        assert cfg.network_enabled is False
        assert cfg.working_directory is None
        assert cfg.environment is None
        assert cfg.allowed_commands is None

    def test_custom(self):
        cfg = SandboxConfig(
            timeout_seconds=10.0,
            max_output_bytes=50_000,
            memory_limit_mb=512,
            network_enabled=True,
            working_directory="/tmp/sandbox",
            environment={"FOO": "bar"},
            allowed_commands=["python3", "git"],
        )
        assert cfg.timeout_seconds == 10.0
        assert cfg.memory_limit_mb == 512
        assert cfg.network_enabled is True
        assert cfg.environment["FOO"] == "bar"
        assert len(cfg.allowed_commands) == 2


class TestExecutionResult:
    def test_defaults(self):
        r = ExecutionResult(exit_code=0)
        assert r.exit_code == 0
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.timed_out is False
        assert r.duration_seconds == 0.0
        assert r.resource_usage == {}

    def test_with_output(self):
        r = ExecutionResult(
            exit_code=1,
            stdout="hello",
            stderr="error msg",
            timed_out=False,
            duration_seconds=1.5,
            resource_usage={"peak_memory_mb": 128},
        )
        assert r.exit_code == 1
        assert r.stdout == "hello"
        assert r.resource_usage["peak_memory_mb"] == 128


class TestSandboxSession:
    def test_is_abstract(self):
        assert hasattr(SandboxSession, "execute_shell")
        assert hasattr(SandboxSession, "execute_python")
        assert hasattr(SandboxSession, "close")
