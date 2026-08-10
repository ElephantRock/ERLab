"""Typed message bus for pub-sub agent communication.

Supports topic-based subscription where agents listen for specific
message types rather than being called in sequence.

Reference: agentscope MsgHub pub-sub broadcasting, autogen @message_handler
decorator for type-based routing.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MessagePriority(int, Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class AgentMessage:
    """Typed message for inter-agent communication."""

    message_type: str
    payload: Any
    sender_id: str
    recipient_id: str | None = None  # None = broadcast to topic subscribers
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)

    @property
    def is_broadcast(self) -> bool:
        return self.recipient_id is None


# Type alias for async message handlers
MessageHandler = Callable[[AgentMessage], Coroutine[Any, Any, None]]


class MessageBus:
    """Pub-sub message bus for multi-agent coordination.

    Agents subscribe to message types (topics). When a message is published,
    all subscribers to that topic receive it. Supports both broadcast and
    direct (point-to-point) messaging.
    """

    def __init__(self):
        self._subscribers: dict[str, list[tuple[str, MessageHandler]]] = defaultdict(list)
        self._history: list[AgentMessage] = []
        self._max_history = 1000

    def subscribe(self, agent_id: str, message_type: str, handler: MessageHandler) -> None:
        """Subscribe an agent to a message type (topic)."""
        self._subscribers[message_type].append((agent_id, handler))
        logger.debug("Agent %s subscribed to topic '%s'", agent_id, message_type)

    def unsubscribe(self, agent_id: str, message_type: str) -> None:
        """Remove an agent's subscription from a topic."""
        self._subscribers[message_type] = [
            (aid, h) for aid, h in self._subscribers[message_type] if aid != agent_id
        ]

    async def publish(self, message: AgentMessage) -> int:
        """Publish a message. Returns number of subscribers that received it.

        For broadcast messages (recipient_id=None), delivers to all topic subscribers.
        For direct messages, delivers only to the matching subscriber.
        """
        self._history.append(message)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

        subscribers = self._subscribers.get(message.message_type, [])
        if not subscribers:
            logger.debug("No subscribers for topic '%s'", message.message_type)
            return 0

        tasks = []
        for agent_id, handler in subscribers:
            if message.recipient_id and agent_id != message.recipient_id:
                continue
            tasks.append(self._safe_deliver(handler, message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return len(tasks)

    async def publish_and_collect(
        self,
        message: AgentMessage,
        timeout: float = 30.0,
    ) -> list[Any]:
        """Publish a message and collect responses from subscribers.

        Returns a list of responses. Each handler should store its response
        in message.metadata['response'] or use a shared state object.
        """
        subscribers = self._subscribers.get(message.message_type, [])
        if not subscribers:
            return []

        responses: list[Any] = []
        response_event = asyncio.Event()
        remaining = len(subscribers)

        async def collecting_handler(wrapper_handler: MessageHandler, msg: AgentMessage):
            await wrapper_handler(msg)
            response = msg.metadata.get("response")
            if response is not None:
                responses.append(response)
            nonlocal remaining
            remaining -= 1
            if remaining <= 0:
                response_event.set()

        tasks = []
        for agent_id, handler in subscribers:
            if message.recipient_id and agent_id != message.recipient_id:
                continue
            tasks.append(collecting_handler(handler, message))

        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout,
            )
        except TimeoutError:
            logger.warning("publish_and_collect timed out after %.1fs", timeout)

        return responses

    def get_history(
        self,
        message_type: str | None = None,
        agent_id: str | None = None,
        limit: int = 50,
    ) -> list[AgentMessage]:
        """Retrieve message history, optionally filtered by type or agent."""
        results = self._history
        if message_type:
            results = [m for m in results if m.message_type == message_type]
        if agent_id:
            results = [m for m in results if m.sender_id == agent_id or m.recipient_id == agent_id]
        return results[-limit:]

    @property
    def topic_count(self) -> int:
        return len(self._subscribers)

    @property
    def subscriber_count(self) -> int:
        return sum(len(subs) for subs in self._subscribers.values())

    @staticmethod
    async def _safe_deliver(handler: MessageHandler, message: AgentMessage):
        """Deliver message to handler, catching exceptions."""
        try:
            await handler(message)
        except Exception as e:
            logger.error(
                "Message handler failed for topic '%s': %s",
                message.message_type,
                e,
            )
