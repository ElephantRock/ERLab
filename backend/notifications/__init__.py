"""Webhook notification module (BATCH-32)."""

from backend.notifications.dispatch import create_notification
from backend.notifications.webhooks import fire_webhook

__all__ = ["fire_webhook", "create_notification"]
