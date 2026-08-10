"""ReAct-style tool-calling mixin for agents.

Provides a tool loop: LLM + tool schemas → tool_calls → execute → feed back.
Agents can mix this in to gain tool use capability.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.pipeline.tools.registry import ToolRegistry
    from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class ToolCallingMixin:
    """ReAct-style tool-calling loop for agents.

    Usage:
        class MyAgent(ToolCallingMixin):
            def __init__(self, provider, tool_registry=None):
                ToolCallingMixin.__init__(self, provider, tool_registry)

            async def run(self, messages):
                return await self.run_tool_loop(messages)
    """

    def __init__(
        self,
        provider: LLMProvider,
        tool_registry: ToolRegistry | None = None,
    ):
        self._tool_provider = provider
        self._tool_registry = tool_registry
        self._max_tool_iterations = 5

    async def run_tool_loop(
        self,
        messages: list[dict],
        max_iterations: int | None = None,
    ) -> str:
        """Run a ReAct-style tool loop. Returns the final text response."""
        if not self._tool_registry or not self._tool_registry.list_tools():
            return await self._tool_provider.complete(messages)

        tools = self._tool_registry.get_schemas()
        max_iters = max_iterations or self._max_tool_iterations
        current_messages = list(messages)

        response = None
        for _ in range(max_iters):
            response = await self._tool_provider.complete_with_tools(
                messages=current_messages,
                tools=tools,
                temperature=0.3,
            )

            if not response.structured or "tool_calls" not in response.structured:
                return response.content

            # Execute each tool call
            tool_results = await self._execute_tool_calls(response.structured["tool_calls"])

            # Feed tool results back
            current_messages.append({
                "role": "assistant",
                "content": response.content,
                "tool_calls": response.structured["tool_calls"],
            })
            for tr in tool_results:
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tr["tool_call_id"],
                    "content": tr["result"],
                })

        return response.content if response and response.content else ""

    async def _execute_tool_calls(self, tool_calls: list[dict]) -> list[dict]:
        """Execute a batch of tool calls and return results."""
        results = []
        for tc in tool_calls:
            try:
                args = json.loads(tc["arguments"]) if isinstance(tc["arguments"], str) else tc["arguments"]
                result = await self._tool_registry.call(tc["name"], **args)  # type: ignore[union-attr]
                results.append({
                    "tool_call_id": tc.get("id", ""),
                    "result": json.dumps(result) if not isinstance(result, str) else result,
                })
            except Exception as e:
                logger.warning("Tool '%s' call failed: %s", tc.get("name"), e)
                results.append({
                    "tool_call_id": tc.get("id", ""),
                    "result": f"Error: {e}",
                })
        return results
