"""ASGI middleware enforcing a strict pre-parser body size cap on the
diagnostics runtime-error endpoint.

F1.6.1 [V3-4]: the 8 KiB cap MUST run before FastAPI/Pydantic body
parsing. A normal route handler signature causes the framework to read
and parse the request before the handler executes, so a size check
inside the route is too late. This middleware intercepts the ASGI
``receive`` callable and stops reading once cumulative body bytes
exceed the cap, returning a 413 response BEFORE the route handler runs.

Scope is intentionally narrow: ONLY ``POST /api/v1/diagnostics/runtime-error``
is intercepted. All other paths/methods pass through unchanged.

Chunked-transfer-encoding safe: the cap accumulates across multiple
``receive`` events.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

# 8 KiB. Generous enough for a single sanitized runtime-error report
# (event_id, category, route, normalized message, bounded component
# stack, build version) but small enough to reject abuse.
MAX_BODY_BYTES = 8 * 1024

TARGET_PATH = "/api/v1/diagnostics/runtime-error"
TARGET_METHOD = "POST"


class DiagnosticsBodyLimitMiddleware:
    """Pure ASGI middleware (Starlette/Built middleware protocol).

    ``app.add_middleware`` in FastAPI accepts either a class with this
    signature or a Starlette ``Middleware`` object. We use the class form
    so the middleware can be added via ``app.add_middleware`` without
    additional wrapper code.
    """

    def __init__(
        self,
        app: Callable[
            [MutableMapping[str, Any], Callable, Callable],
            Awaitable[None],
        ],
    ) -> None:
        self.app = app

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
    ) -> None:
        if not self._is_target(scope):
            await self.app(scope, receive, send)
            return

        # Wrap receive so we can count bytes and short-circuit.
        cumulative = {"bytes": 0, "rejected": False}

        async def capped_receive() -> MutableMapping[str, Any]:
            event = await receive()
            if event.get("type") != "http.request":
                return event
            body_chunk: bytes = event.get("body", b"") or b""
            cumulative["bytes"] += len(body_chunk)
            more_body = bool(event.get("more_body", False))
            if cumulative["bytes"] > MAX_BODY_BYTES and not cumulative["rejected"]:
                cumulative["rejected"] = True
                # Stop reading. Signal end-of-body so downstream does not hang.
                return {
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }
            return {
                "type": "http.request",
                "body": body_chunk,
                "more_body": more_body,
            }

        rejected = False

        async def guarded_send(message: MutableMapping[str, Any]) -> None:
            # If the body cap tripped, intercept the downstream response
            # start and substitute a 413 BEFORE the route handler logic
            # runs. The handler will not be entered because the receive
            # stream is truncated; FastAPI's body parser will fail to
            # construct the model and emit its own 422, which we override
            # here.
            nonlocal rejected
            if message.get("type") == "http.response.start" and cumulative["rejected"]:
                rejected = True
                await _send_413(send)
                return
            if rejected:
                # Discard the body of the substituted handler response.
                return
            await send(message)

        try:
            await self.app(scope, capped_receive, guarded_send)
        except Exception:
            # If the truncated body caused a parser exception, prefer the
            # 413 over a 500. The cap is the load-bearing signal.
            if cumulative["rejected"] and not rejected:
                await _send_413(send)
                return
            raise

        # If the handler never started because the cap tripped on the
        # first receive and the app returned without sending a response,
        # emit the 413 ourselves.
        if cumulative["rejected"] and not rejected:
            await _send_413(send)

    @staticmethod
    def _is_target(scope: MutableMapping[str, Any]) -> bool:
        if scope.get("type") != "http":
            return False
        method = scope.get("method", "")
        path = scope.get("path", "")
        return method == TARGET_METHOD and path == TARGET_PATH


async def _send_413(send: Callable[[MutableMapping[str, Any]], Awaitable[None]]) -> None:
    """Emit a 413 Payload Too Large response with a JSON body."""
    body = json.dumps(
        {
            "error": {
                "code": "PAYLOAD_TOO_LARGE",
                "message": (
                    f"Runtime-error report body exceeds the {MAX_BODY_BYTES}-byte limit."
                ),
            }
        }
    ).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": body,
            "more_body": False,
        }
    )
