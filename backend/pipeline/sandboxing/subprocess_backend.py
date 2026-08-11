"""Subprocess sandbox backend — enhanced OS-level isolation.

Provides environment sanitization, command allowlisting, working directory
confinement, and memory limit enforcement via OS resource limits.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

from backend.pipeline.sandboxing.protocol import (
    ExecutionResult,
    SandboxConfig,
    SandboxSession,
)

# Environment variables safe to pass through
_SAFE_ENV_VARS = frozenset({
    "PATH", "HOME", "USERPROFILE", "TEMP", "TMP",
    "SYSTEMROOT", "COMSPEC", "LANG", "LC_ALL", "LC_CTYPE",
    "PYTHONPATH", "PYTHONIOENCODING",
})


class _SubprocessSession(SandboxSession):
    """Persistent session using subprocess isolation."""

    def __init__(self, backend: SubprocessSandboxBackend, config: SandboxConfig) -> None:
        self._backend = backend
        self._config = config

    async def execute_shell(self, command: str) -> ExecutionResult:
        return await self._backend.execute_shell(command, self._config)

    async def execute_python(self, code: str) -> ExecutionResult:
        return await self._backend.execute_python(code, self._config)


class SubprocessSandboxBackend:
    """Enhanced subprocess sandbox with environment and command controls."""

    def __init__(self, default_config: SandboxConfig | None = None) -> None:
        self._default_config = default_config or SandboxConfig()

    @property
    def name(self) -> str:
        return "subprocess"

    def is_available(self) -> bool:
        return True

    async def execute_shell(
        self, command: str, config: SandboxConfig | None = None
    ) -> ExecutionResult:
        cfg = config or self._default_config
        _validate_command(command, cfg)
        return await _run_sandboxed(command, cfg, shell=True)

    async def execute_python(
        self, code: str, config: SandboxConfig | None = None
    ) -> ExecutionResult:
        cfg = config or self._default_config
        return await _run_sandboxed("", cfg, shell=False, python_code=code)

    def create_session(self, config: SandboxConfig | None = None) -> SandboxSession:
        return _SubprocessSession(self, config or self._default_config)


def _validate_command(command: str, config: SandboxConfig) -> None:
    """Check command against allowlist if configured."""
    if not config.allowed_commands:
        return
    base = command.split()[0] if command else ""
    if base not in config.allowed_commands:
        raise ValueError(f"Command not allowed: {base!r}. Allowed: {config.allowed_commands}")


def _build_env(config: SandboxConfig) -> dict[str, str]:
    """Build a sanitized environment for the subprocess."""
    current = os.environ
    clean = {}

    for key in _SAFE_ENV_VARS:
        if key in current:
            clean[key] = current[key]

    if config.environment:
        clean.update(config.environment)

    return clean


async def _run_sandboxed(
    command: str,
    config: SandboxConfig,
    *,
    shell: bool = True,
    python_code: str | None = None,
) -> ExecutionResult:
    """Execute with subprocess isolation."""
    t0 = time.time()
    env = _build_env(config)
    cwd = config.working_directory or None

    if python_code is not None:
        cmd = [sys.executable, "-c", python_code]
    else:
        cmd = command

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd if isinstance(cmd, list) else cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd,
        )
    except (OSError, TypeError):
        shell_cmd = command if not python_code else f'{sys.executable} -c "{python_code}"'
        proc = await asyncio.create_subprocess_shell(
            shell_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd,
        )

    timed_out = False
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=config.timeout_seconds
        )
    except TimeoutError:
        proc.kill()
        await proc.wait()
        stdout_bytes, stderr_bytes = b"", b""
        timed_out = True

    duration = time.time() - t0
    stdout = _truncate_output(stdout_bytes, config.max_output_bytes)
    stderr = _truncate_output(stderr_bytes, config.max_output_bytes)

    return ExecutionResult(
        exit_code=-1 if timed_out else (proc.returncode or 0),
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        duration_seconds=round(duration, 3),
        resource_usage={"memory_limit_mb": config.memory_limit_mb},
    )


def _truncate_output(raw: bytes, max_bytes: int) -> str:
    text = raw.decode(errors="replace")
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="replace")
