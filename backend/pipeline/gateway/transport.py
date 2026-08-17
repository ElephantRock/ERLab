"""Typed gateway transport failure (Q2).

Case-3 qualification (3B–3D specimens) proved that provider/transport
failures — including a fully unavailable LM Studio endpoint — were
converted into success-shaped ``LLMResponse(content="", degraded=True)``
objects by the gateway catch-all. Upstream, a dead endpoint was
indistinguishable from an empty completion, and stages continued on
empty output until an empty pipeline could report ``succeeded``.

This module gives transport/provider execution failure its identity
back. The gateway re-raises these instead of empty-content responses;
``GatewayProvider`` propagates them instead of falling back to the
same failed inner provider. The existing ``StageExecutor`` bounded
retries and typed stage-failure machinery take over from there.

Scope note (per the Q2 authorization): HTTP-success/200-style empty
completions are a DIFFERENT failure class and stay non-degraded —
no empty-rate threshold, circuit-breaker policy, or per-caller retry
is added here.
"""
from __future__ import annotations


class GatewayTransportError(RuntimeError):
    """A gateway LLM call failed at the provider/transport layer.

    Raised for connection failures, timeouts, and other execution
    errors that mean the call never produced a usable response — as
    opposed to a successful call whose content is empty or
    unparseable. Carries the task name and the underlying cause for
    diagnostics.
    """

    def __init__(self, task: str, cause: str) -> None:
        self.task = task
        self.cause = cause
        super().__init__(
            f"Gateway LLM call failed (transport/provider) for task"
            f" {task!r}: {cause}"
        )
