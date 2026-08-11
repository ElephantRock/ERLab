"""Webhook notification dispatcher (BATCH-32).

Fires HTTP POST requests to a configured webhook URL on pipeline events
(completion, failure). Webhook failures are logged but never block the
pipeline — aligns with HB-01 (resilient, non-blocking).
"""

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

# Shared async client (reused across calls, lazy-initialised)
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=10.0)
    return _client


def _build_signature(payload: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


async def fire_webhook(event_type: str, payload: dict[str, Any]) -> None:
    """Fire a webhook notification.

    Silently returns if webhooks are disabled or no URL is configured.
    Logs a warning on failure but never raises — the pipeline must not
    be blocked by a notification failure.

    Args:
        event_type: Event identifier (e.g. "pipeline.completed").
        payload: JSON-serialisable dict sent as the request body.
    """
    settings = get_settings()
    if not settings.webhook_enabled or not settings.webhook_url:
        return

    body = {
        "event": event_type,
        "timestamp": datetime.now(UTC).isoformat(),
        "data": payload,
    }

    try:
        client = _get_client()
        headers: dict[str, str] = {"Content-Type": "application/json"}
        raw = json.dumps(body).encode()

        if settings.webhook_secret:
            sig = _build_signature(raw, settings.webhook_secret)
            headers["X-Webhook-Signature"] = sig

        resp = await client.post(settings.webhook_url, content=raw, headers=headers)
        if resp.status_code >= 400:
            logger.warning(
                "Webhook %s returned status %d: %s",
                settings.webhook_url,
                resp.status_code,
                resp.text[:200],
            )
        else:
            logger.info(
                "Webhook fired: event=%s status=%d",
                event_type,
                resp.status_code,
            )
    except Exception:
        logger.warning("Webhook delivery failed for event=%s", event_type, exc_info=True)
