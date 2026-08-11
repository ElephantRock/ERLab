"""Sandbox manager — auto-detection, backend coordination, and convenience API.

Central point of access for sandboxed execution. Auto-detects the strongest
available backend (Docker > Subprocess > Noop) or allows explicit selection.
"""

from __future__ import annotations

import logging

from backend.pipeline.sandboxing.docker_backend import DockerSandboxBackend
from backend.pipeline.sandboxing.noop_backend import NoopSandboxBackend
from backend.pipeline.sandboxing.protocol import (
    ExecutionResult,
    SandboxBackend,
    SandboxConfig,
    SandboxSession,
)
from backend.pipeline.sandboxing.subprocess_backend import SubprocessSandboxBackend

logger = logging.getLogger(__name__)

_BACKEND_ORDER: list[str] = ["docker", "subprocess", "noop"]


class SandboxManager:
    """Central coordinator for sandbox backends."""

    def __init__(
        self,
        backend_name: str = "auto",
        default_config: SandboxConfig | None = None,
        shell_image: str = "alpine:3.19",
        python_image: str = "python:3.11-slim",
    ) -> None:
        self._backend_name = backend_name
        self._default_config = default_config or SandboxConfig()
        self._shell_image = shell_image
        self._python_image = python_image
        self._backends: dict[str, SandboxBackend] = {}
        self._active: SandboxBackend | None = None

        self._init_backends()

    def _init_backends(self) -> None:
        """Pre-register all backend instances."""
        self._backends["noop"] = NoopSandboxBackend(self._default_config)
        self._backends["subprocess"] = SubprocessSandboxBackend(self._default_config)
        self._backends["docker"] = DockerSandboxBackend(
            self._default_config,
            shell_image=self._shell_image,
            python_image=self._python_image,
        )

    def detect_backend(self) -> SandboxBackend:
        """Auto-detect the strongest available backend."""
        if self._backend_name != "auto":
            backend = self._backends.get(self._backend_name)
            if backend is None:
                logger.warning("Unknown backend %r, falling back to noop", self._backend_name)
                return self._backends["noop"]
            if not backend.is_available():
                logger.warning(
                    "Requested backend %r not available, falling back to noop",
                    self._backend_name,
                )
                return self._backends["noop"]
            return backend

        for name in _BACKEND_ORDER:
            backend = self._backends[name]
            if backend.is_available():
                logger.info("Auto-detected sandbox backend: %s", name)
                return backend

        # Should never reach here since noop is always available
        return self._backends["noop"]

    @property
    def active_backend(self) -> SandboxBackend:
        """Lazily resolve and cache the active backend."""
        if self._active is None:
            self._active = self.detect_backend()
        return self._active

    @property
    def backend_name(self) -> str:
        return self.active_backend.name

    async def execute_shell(
        self, command: str, config: SandboxConfig | None = None
    ) -> ExecutionResult:
        """Execute a shell command in the sandbox."""
        return await self.active_backend.execute_shell(command, config)

    async def execute_python(
        self, code: str, config: SandboxConfig | None = None
    ) -> ExecutionResult:
        """Execute Python code in the sandbox."""
        return await self.active_backend.execute_python(code, config)

    def create_session(self, config: SandboxConfig | None = None) -> SandboxSession:
        """Create a persistent sandbox session."""
        backend = self.active_backend
        if not hasattr(backend, "create_session"):
            raise RuntimeError(
                f"Backend {backend.name!r} does not support persistent sessions"
            )
        return backend.create_session(config or self._default_config)  # type: ignore[union-attr]

    def get_backend(self, name: str) -> SandboxBackend | None:
        """Get a specific backend by name."""
        return self._backends.get(name)

    def list_backends(self) -> dict[str, bool]:
        """List all registered backends and their availability."""
        return {name: b.is_available() for name, b in self._backends.items()}


# Module-level singleton
_manager: SandboxManager | None = None


def get_sandbox_manager() -> SandboxManager:
    global _manager
    if _manager is None:
        _manager = SandboxManager()
    return _manager


def reset_sandbox_manager() -> None:
    """Reset the singleton — mainly for testing."""
    global _manager
    _manager = None
