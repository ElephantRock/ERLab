"""Core abstractions for the sandboxing subsystem.

Defines the configuration, result types, and backend protocol that all
sandbox implementations must satisfy.
"""

from __future__ import annotations

import abc
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class SandboxConfig(BaseModel):
    """Per-execution sandbox resource limits."""

    timeout_seconds: float = 30.0
    max_output_bytes: int = 100_000
    memory_limit_mb: int = 256
    network_enabled: bool = False
    working_directory: str | None = None
    environment: dict[str, str] | None = None
    allowed_commands: list[str] | None = None


class ExecutionResult(BaseModel):
    """Result of a sandboxed execution."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_seconds: float = 0.0
    resource_usage: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class SandboxBackend(Protocol):
    """Protocol for sandbox backends. Duck-typed — no inheritance required."""

    @property
    def name(self) -> str: ...

    def is_available(self) -> bool: ...

    async def execute_shell(
        self, command: str, config: SandboxConfig | None = None
    ) -> ExecutionResult: ...

    async def execute_python(
        self, code: str, config: SandboxConfig | None = None
    ) -> ExecutionResult: ...


class SandboxSession(abc.ABC):
    """Persistent sandbox session — reuse across multiple executions."""

    @abc.abstractmethod
    async def execute_shell(self, command: str) -> ExecutionResult: ...

    @abc.abstractmethod
    async def execute_python(self, code: str) -> ExecutionResult: ...

    async def close(self) -> None:
        """Clean up session resources. Default is no-op."""

    async def __aenter__(self) -> SandboxSession:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
