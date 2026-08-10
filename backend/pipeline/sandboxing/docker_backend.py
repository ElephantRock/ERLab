"""Docker-based sandbox backend — container isolation via Docker CLI.

Uses the `docker` CLI directly (no Python SDK dependency). Requires
Docker Desktop or Docker Engine to be running on the host.
"""

from __future__ import annotations

import asyncio
import logging
import time

from backend.pipeline.sandboxing.protocol import (
    ExecutionResult,
    SandboxConfig,
    SandboxSession,
)

logger = logging.getLogger(__name__)

_DEFAULT_SHELL_IMAGE = "alpine:3.19"
_DEFAULT_PYTHON_IMAGE = "python:3.11-slim"
_AVAILABILITY_CACHE_TTL = 60.0


class _DockerSession(SandboxSession):
    """Persistent Docker session using a long-running container."""

    def __init__(
        self,
        container_id: str,
        config: SandboxConfig,
        shell_image: str,
        python_image: str,
    ) -> None:
        self._container_id = container_id
        self._config = config
        self._shell_image = shell_image
        self._python_image = python_image
        self._closed = False

    async def execute_shell(self, command: str) -> ExecutionResult:
        if self._closed:
            raise RuntimeError("Session is closed")
        return await _docker_exec(self._container_id, command, self._config)

    async def execute_python(self, code: str) -> ExecutionResult:
        if self._closed:
            raise RuntimeError("Session is closed")
        escaped = code.replace("'", "'\\''")
        cmd = f"python3 -c '{escaped}'"
        return await _docker_exec(self._container_id, cmd, self._config)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", self._container_id,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except OSError:
            pass


class DockerSandboxBackend:
    """Sandbox backend using Docker containers for full process isolation."""

    def __init__(
        self,
        default_config: SandboxConfig | None = None,
        shell_image: str = _DEFAULT_SHELL_IMAGE,
        python_image: str = _DEFAULT_PYTHON_IMAGE,
    ) -> None:
        self._default_config = default_config or SandboxConfig()
        self._shell_image = shell_image
        self._python_image = python_image
        self._available: bool | None = None
        self._last_check: float = 0.0

    @property
    def name(self) -> str:
        return "docker"

    def is_available(self) -> bool:
        now = time.time()
        if self._available is not None and (now - self._last_check) < _AVAILABILITY_CACHE_TTL:
            return self._available

        try:
            proc = asyncio.run(_docker_info())
            self._available = proc.returncode == 0
        except Exception:
            self._available = False

        self._last_check = now
        if self._available:
            logger.info("Docker backend available (image: %s)", self._shell_image)
        else:
            logger.debug("Docker backend not available")
        return self._available

    async def check_available_async(self) -> bool:
        """Async version of availability check."""
        now = time.time()
        if self._available is not None and (now - self._last_check) < _AVAILABILITY_CACHE_TTL:
            return self._available

        try:
            proc = await _docker_info()
            self._available = proc.returncode == 0
        except Exception:
            self._available = False

        self._last_check = now
        return self._available

    async def execute_shell(
        self, command: str, config: SandboxConfig | None = None
    ) -> ExecutionResult:
        cfg = config or self._default_config
        return await _docker_run(command, cfg, self._shell_image)

    async def execute_python(
        self, code: str, config: SandboxConfig | None = None
    ) -> ExecutionResult:
        cfg = config or self._default_config
        escaped = code.replace("'", "'\\''")
        cmd = f"python3 -c '{escaped}'"
        return await _docker_run(cmd, cfg, self._python_image)

    async def create_session(self, config: SandboxConfig | None = None) -> SandboxSession:
        """Create a persistent Docker container session."""
        cfg = config or self._default_config
        container_id = await _start_container(cfg, self._shell_image)
        return _DockerSession(container_id, cfg, self._shell_image, self._python_image)


async def _docker_info() -> asyncio.subprocess.Process:
    proc = await asyncio.create_subprocess_exec(
        "docker", "info",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    return proc


async def _docker_run(command: str, config: SandboxConfig, image: str) -> ExecutionResult:
    """Run a command in a fresh Docker container."""
    t0 = time.time()
    args = _build_run_args(command, config, image)

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
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

    except FileNotFoundError:
        return ExecutionResult(
            exit_code=-1, stderr="docker CLI not found", timed_out=False,
            duration_seconds=time.time() - t0,
        )

    duration = time.time() - t0
    return ExecutionResult(
        exit_code=-1 if timed_out else (proc.returncode or 0),
        stdout=_truncate(stdout_bytes, config.max_output_bytes),
        stderr=_truncate(stderr_bytes, config.max_output_bytes),
        timed_out=timed_out,
        duration_seconds=round(duration, 3),
    )


async def _docker_exec(container_id: str, command: str, config: SandboxConfig) -> ExecutionResult:
    """Execute a command in an existing container."""
    t0 = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", container_id, "sh", "-c", command,
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

    except FileNotFoundError:
        return ExecutionResult(
            exit_code=-1, stderr="docker CLI not found",
            duration_seconds=time.time() - t0,
        )

    duration = time.time() - t0
    return ExecutionResult(
        exit_code=-1 if timed_out else (proc.returncode or 0),
        stdout=_truncate(stdout_bytes, config.max_output_bytes),
        stderr=_truncate(stderr_bytes, config.max_output_bytes),
        timed_out=timed_out,
        duration_seconds=round(duration, 3),
    )


def _build_run_args(command: str, config: SandboxConfig, image: str) -> list[str]:
    """Build docker run CLI arguments."""
    args = ["docker", "run", "--rm"]

    if not config.network_enabled:
        args.append("--network=none")

    if config.memory_limit_mb:
        args.extend(["--memory", f"{config.memory_limit_mb}m"])

    if config.working_directory:
        args.extend(["-w", config.working_directory])

    for key, value in (config.environment or {}).items():
        args.extend(["-e", f"{key}={value}"])

    args.extend([image, "sh", "-c", command])
    return args


async def _start_container(config: SandboxConfig, image: str) -> str:
    """Start a persistent container and return its ID."""
    args = ["docker", "run", "-d"]

    if not config.network_enabled:
        args.append("--network=none")

    if config.memory_limit_mb:
        args.extend(["--memory", f"{config.memory_limit_mb}m"])

    args.extend([image, "sleep", "infinity"])

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode().strip()


def _truncate(raw: bytes, max_bytes: int) -> str:
    text = raw.decode(errors="replace")
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="replace")
