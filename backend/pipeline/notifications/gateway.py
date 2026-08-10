"""Notification gateway for pipeline events.

Ported from huggingface/ml-intern messaging/gateway.py pattern.
Provides abstract notification interface with console and webhook implementations.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class PipelineEvent(str, Enum):
    """Pipeline events that can trigger notifications."""

    RUN_STARTED = "run_started"
    STAGE_COMPLETED = "stage_completed"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    DOOM_DETECTED = "doom_detected"


@dataclass
class Notification:
    """A notification payload."""

    event: PipelineEvent
    run_id: str
    strategy: str
    domain: str
    message: str
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event.value,
            "run_id": self.run_id,
            "strategy": self.strategy,
            "domain": self.domain,
            "message": self.message,
            "data": self.data or {},
        }


class NotificationGateway(ABC):
    """Abstract base for notification dispatchers."""

    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """Send a notification. Returns True if successful."""
        ...


class ConsoleNotifier(NotificationGateway):
    """Log notifications to stdout. Always available."""

    async def send(self, notification: Notification) -> bool:
        level = logging.INFO
        if notification.event == PipelineEvent.RUN_FAILED:
            level = logging.ERROR
        elif notification.event == PipelineEvent.DOOM_DETECTED:
            level = logging.WARNING
        logger.log(
            level,
            "[NOTIFY] %s | %s | %s | %s",
            notification.event.value,
            notification.run_id,
            notification.domain,
            notification.message,
        )
        return True


class WebhookNotifier(NotificationGateway):
    """POST notifications to a configurable URL."""

    def __init__(self, url: str, timeout: float = 5.0):
        self.url = url
        self.timeout = timeout

    async def send(self, notification: Notification) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.url,
                    json=notification.to_dict(),
                    headers={"Content-Type": "application/json"},
                )
                if response.status_code < 400:
                    logger.debug(
                        "Webhook notification sent to %s: %s",
                        self.url, notification.event.value,
                    )
                    return True
                else:
                    logger.warning(
                        "Webhook returned %d for %s",
                        response.status_code, self.url,
                    )
                    return False
        except Exception as e:
            logger.warning("Webhook notification failed: %s", e)
            return False


class CompositeNotifier(NotificationGateway):
    """Dispatches to multiple notifiers."""

    def __init__(self, notifiers: list[NotificationGateway]):
        self.notifiers = notifiers

    async def send(self, notification: Notification) -> bool:
        results = []
        for notifier in self.notifiers:
            try:
                results.append(await notifier.send(notification))
            except Exception as e:
                logger.warning("Notifier %s failed: %s", type(notifier).__name__, e)
                results.append(False)
        return any(results)


def create_notifier(
    webhook_url: str | None = None,
) -> NotificationGateway:
    """Factory: create a notifier based on configuration.

    Always includes ConsoleNotifier. If webhook_url is provided,
    also includes WebhookNotifier.
    """
    notifiers: list[NotificationGateway] = [ConsoleNotifier()]
    if webhook_url:
        notifiers.append(WebhookNotifier(webhook_url))
    if len(notifiers) == 1:
        return notifiers[0]
    return CompositeNotifier(notifiers)
