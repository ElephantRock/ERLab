"""Sandboxing subsystem — pluggable execution isolation for untrusted code.

Backends: Docker (strongest), Subprocess (enhanced), Noop (pass-through).
Auto-detects the strongest available backend. Feature-flagged via config.
"""

from backend.pipeline.sandboxing.manager import SandboxManager, get_sandbox_manager
from backend.pipeline.sandboxing.protocol import (
    ExecutionResult,
    SandboxBackend,
    SandboxConfig,
    SandboxSession,
)

__all__ = [
    "ExecutionResult",
    "SandboxBackend",
    "SandboxConfig",
    "SandboxManager",
    "SandboxSession",
    "get_sandbox_manager",
]
