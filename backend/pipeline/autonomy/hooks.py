"""Hook dispatch system for pipeline events.

DeepAgents-inspired hook dispatch that allows registering handlers
for pipeline events (session.start, pipeline.complete, gap.found, etc.).
"""

import asyncio
import logging
from collections import defaultdict
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

# Standard event names
EVENT_SESSION_START = "session.start"
EVENT_SESSION_END = "session.end"
EVENT_PIPELINE_START = "pipeline.start"
EVENT_PIPELINE_STAGE_COMPLETE = "pipeline.stage.complete"
EVENT_PIPELINE_COMPLETE = "pipeline.complete"
EVENT_GAP_FOUND = "gap.found"
EVENT_IDEA_GENERATED = "idea.generated"
EVENT_IDEA_SCORED = "idea.scored"
EVENT_IMPASSE_DETECTED = "impasse.detected"
EVENT_IMPASSE_RESOLVED = "impasse.resolved"
EVENT_STATE_TRANSITION = "state.transition"

HookHandler = Callable[[dict], Awaitable[None]]


class HookDispatcher:
    """DeepAgents-inspired hook dispatch for pipeline events."""

    def __init__(self):
        self._handlers: dict[str, list[HookHandler]] = defaultdict(list)

    def register(self, event: str, handler: HookHandler) -> None:
        """Register an async handler for an event."""
        self._handlers[event].append(handler)

    def unregister(self, event: str, handler: HookHandler) -> None:
        """Remove a handler for an event."""
        if event in self._handlers:
            self._handlers[event] = [h for h in self._handlers[event] if h != handler]

    async def dispatch(self, event: str, payload: dict | None = None) -> None:
        """Fire all handlers registered for an event."""
        handlers = self._handlers.get(event, [])
        if not handlers:
            return

        for handler in handlers:
            try:
                await handler(payload or {})
            except Exception as e:
                logger.error("Hook handler failed for event %s: %s", event, e)

    async def dispatch_sync_safe(self, event: str, payload: dict | None = None) -> None:
        """Dispatch and log errors but never raise."""
        try:
            await self.dispatch(event, payload)
        except Exception as e:
            logger.error("Hook dispatch failed for %s: %s", event, e)

    @property
    def registered_events(self) -> list[str]:
        return list(self._handlers.keys())
