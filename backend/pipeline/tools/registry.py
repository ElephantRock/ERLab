"""Tool registry with @tool decorator — OpenAI Agents-inspired pattern.

Agents discover and call tools by name. Tools are registered with a schema
describing their parameters, and an async handler function.

Usage:
    from backend.pipeline.tools.registry import tool, get_tool_registry

    @tool(description="Search arXiv for papers")
    async def literature_search(query: str, max_results: int = 10) -> list[dict]:
        ...

    registry = get_tool_registry()
    results = await registry.call("literature_search", query="attention mechanisms")
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, get_type_hints

from backend.pipeline.tools.tool_limits import (
    TRUSTED_CONFIG,
    UNTRUSTED_CONFIG,
    ToolAuditLog,
    ToolExecutionEvent,
    ToolLimitsConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """A registered tool with its schema and handler."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable
    is_enabled: bool | Callable[[], bool] = True
    guardrail: Any | None = None  # Optional Guardrail for tool-level checking
    timeout: float = 30.0
    trust_level: str = "trusted"  # "trusted" or "untrusted"
    max_output_bytes: int = 1_000_000

    @property
    def enabled(self) -> bool:
        if callable(self.is_enabled):
            return self.is_enabled()
        return self.is_enabled

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling schema format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": [
                        k for k, v in self.parameters.items()
                        if v.get("required", False)
                    ],
                },
            },
        }


def _extract_schema(func: Callable) -> dict[str, Any]:
    """Extract parameter schema from function signature."""
    sig = inspect.signature(func)
    hints = get_type_hints(func) if hasattr(func, "__annotations__") else {}
    params = {}

    type_map = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        list: {"type": "array", "items": {"type": "string"}},
        dict: {"type": "object"},
    }

    for name, param in sig.parameters.items():
        if name == "self":
            continue
        prop: dict[str, Any] = {}
        ann = hints.get(name)
        if ann and ann in type_map:
            prop.update(type_map[ann])
        else:
            prop["type"] = "string"

        if param.default is inspect.Parameter.empty:
            prop["required"] = True
        else:
            prop["default"] = param.default

        params[name] = prop

    return params


class ToolRegistry:
    """Registry of callable tools for agents."""

    def __init__(self, audit_log: ToolAuditLog | None = None) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._audit_log = audit_log

    def register(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        parameters: dict[str, Any] | None = None,
        is_enabled: bool | Callable[[], bool] = True,
        guardrail: Any | None = None,
        timeout: float = 30.0,
        trust_level: str = "trusted",
        max_output_bytes: int = 1_000_000,
    ) -> None:
        """Register a tool. If parameters not provided, extracts from handler signature."""
        params = parameters or _extract_schema(handler)
        self._tools[name] = ToolDefinition(
            name=name,
            description=description or handler.__doc__ or "",
            parameters=params,
            handler=handler,
            is_enabled=is_enabled,
            guardrail=guardrail,
            timeout=timeout,
            trust_level=trust_level,
            max_output_bytes=max_output_bytes,
        )
        logger.info("Registered tool: %s (trust=%s)", name, trust_level)

    def unregister(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self, enabled_only: bool = True) -> list[ToolDefinition]:
        tools = list(self._tools.values())
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        return tools

    def get_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI-format schemas for all enabled tools."""
        return [t.to_openai_schema() for t in self.list_tools(enabled_only=True)]

    async def call(self, name: str, **kwargs: Any) -> Any:
        """Call a tool by name with given arguments."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}. Available: {list(self._tools.keys())}")
        if not tool.enabled:
            raise RuntimeError(f"Tool '{name}' is currently disabled")

        # Tool-level guardrail check
        if tool.guardrail:
            args_str = json.dumps(kwargs, default=str)
            result = tool.guardrail.check(args_str)
            if not result.passed:
                logger.warning("Tool '%s' blocked by guardrail: %s", name, result.blocked_reason)
                self._audit(tool.name, "blocked", 0.0)
                raise RuntimeError(f"Tool '{name}' blocked: {result.blocked_reason}")

        from backend.pipeline.tracing.spans import SpanKind, create_span

        with create_span(SpanKind.TOOL, name, trust=tool.trust_level) as span:
            # Execute with timeout
            t0 = time.time()
            try:
                result = await asyncio.wait_for(
                    tool.handler(**kwargs),
                    timeout=tool.timeout,
                )
            except asyncio.TimeoutError:
                elapsed_ms = (time.time() - t0) * 1000
                self._audit(tool.name, "timeout", elapsed_ms)
                span.set_status("error")
                span.attributes["error"] = "timeout"
                raise RuntimeError(f"Tool '{name}' timed out after {tool.timeout}s")

            elapsed_ms = (time.time() - t0) * 1000
            span.attributes["duration_ms"] = elapsed_ms

            # Output size limit for untrusted tools
            if isinstance(result, str) and len(result.encode()) > tool.max_output_bytes:
                result = result[:tool.max_output_bytes]

            self._audit(tool.name, "success", elapsed_ms)
            logger.info("Tool '%s' called successfully (%.0fms)", name, elapsed_ms)
            return result

    def _audit(self, tool_name: str, status: str, duration_ms: float, error: str | None = None) -> None:
        """Record a tool execution event to the audit log."""
        if self._audit_log:
            self._audit_log.record(ToolExecutionEvent(
                tool_name=tool_name,
                status=status,
                duration_ms=duration_ms,
                error=error,
            ))


def tool(
    name: str | None = None,
    description: str = "",
    parameters: dict[str, Any] | None = None,
    is_enabled: bool | Callable[[], bool] = True,
):
    """Decorator to register a function as a tool.

    Usage:
        @tool(description="Search for papers")
        async def literature_search(query: str, max_results: int = 10) -> list[dict]:
            ...
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        registry = _get_tool_registry()
        registry.register(
            name=tool_name,
            handler=func,
            description=description,
            parameters=parameters,
            is_enabled=is_enabled,
        )
        func._tool_name = tool_name  # type: ignore[attr-defined]
        return func

    return decorator


# Module-level singleton
_registry: ToolRegistry | None = None


def _get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def get_tool_registry() -> ToolRegistry:
    return _get_tool_registry()
