"""Noop sandbox backend — pass-through with timeout and output truncation.

Always available. Uses bare subprocess with minimal resource limits.
This is the fallback when no real isolation is configured.
"""

from __future__ import annotations

import asyncio
import sys
import time

from backend.pipeline.sandboxing.protocol import (
    ExecutionResult,
    SandboxConfig,
    SandboxSession,
)


class _NoopSession(SandboxSession):
    """Persistent session for noop backend — just runs subprocesses."""

    def __init__(self, config: SandboxConfig) -> None:
        self._config = config

    async def execute_shell(self, command: str) -> ExecutionResult:
        return await _run_subprocess(command, self._config, shell=True)

    async def execute_python(self, code: str) -> ExecutionResult:
        cmd = f'{sys.executable} -c {code}'
        return await _run_subprocess(cmd, self._config, shell=False, python_code=code)


class NoopSandboxBackend:
    """Pass-through sandbox with basic timeout and output truncation."""

    def __init__(self, default_config: SandboxConfig | None = None) -> None:
        self._default_config = default_config or SandboxConfig()

    @property
    def name(self) -> str:
        return "noop"

    def is_available(self) -> bool:
        return True

    async def execute_shell(
        self, command: str, config: SandboxConfig | None = None
    ) -> ExecutionResult:
        cfg = config or self._default_config
        return await _run_subprocess(command, cfg, shell=True)

    async def execute_python(
        self, code: str, config: SandboxConfig | None = None
    ) -> ExecutionResult:
        cfg = config or self._default_config
        return await _run_subprocess("", cfg, shell=False, python_code=code)

    def create_session(self, config: SandboxConfig | None = None) -> SandboxSession:
        return _NoopSession(config or self._default_config)


async def _run_subprocess(
    command: str,
    config: SandboxConfig,
    *,
    shell: bool = True,
    python_code: str | None = None,
) -> ExecutionResult:
    """Run a subprocess with timeout and output truncation."""
    t0 = time.time()

    if python_code is not None:
        cmd_args = [sys.executable, "-c", python_code]
    else:
        cmd_args = command

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_args if isinstance(cmd_args, list) else cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except (OSError, TypeError):
        # Fallback for string commands on Windows
        shell_cmd = command if not python_code else f'{sys.executable} -c "{python_code}"'
        proc = await asyncio.create_subprocess_shell(
            shell_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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
    stdout = _truncate(stdout_bytes.decode(errors="replace"), config.max_output_bytes)
    stderr = _truncate(stderr_bytes.decode(errors="replace"), config.max_output_bytes)

    return ExecutionResult(
        exit_code=proc.returncode or -1 if timed_out else (proc.returncode or 0),
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        duration_seconds=round(duration, 3),
    )


def _truncate(text: str, max_bytes: int) -> str:
    """Truncate text to fit within max_bytes when encoded as UTF-8."""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="replace")
