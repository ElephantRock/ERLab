"""API error hierarchy for proper HTTP status codes.

Standardized error format:
    {"error": {"code": "...", "message": "...", "hint": "..."}}

All errors include a status_code, error code string, human-readable message,
and optional remediation hint. The unified error handler in app.py serializes
these into a consistent JSON response with an X-Request-Id header.
"""

from __future__ import annotations


class APIError(Exception):
    """Base API error with HTTP status code, error code, message, and hint.

    Attributes:
        status_code: HTTP status code (e.g. 400, 404, 500).
        code: Machine-readable error code string (e.g. "NOT_FOUND").
        message: Human-readable error description.
        hint: Optional remediation hint for the client.
    """

    def __init__(
        self,
        status_code: int,
        detail: str,
        code: str | None = None,
        hint: str | None = None,
    ):
        self.status_code = status_code
        self.code = code or _status_to_code(status_code)
        self.message = detail
        self.hint = hint
        super().__init__(detail)

    def to_dict(self) -> dict:
        """Serialize to the standardized error format."""
        payload: dict = {
            "code": self.code,
            "message": self.message,
        }
        if self.hint:
            payload["hint"] = self.hint
        return {"error": payload}


class BadRequestError(APIError):
    """400 Bad Request."""

    def __init__(self, detail: str = "Bad request", hint: str | None = None):
        super().__init__(status_code=400, detail=detail, code="BAD_REQUEST", hint=hint)


class UnauthorizedError(APIError):
    """401 Unauthorized."""

    def __init__(self, detail: str = "Invalid or missing API key", hint: str | None = None):
        default_hint = "Provide a valid API key via the X-API-Key header"
        super().__init__(
            status_code=401,
            detail=detail,
            code="UNAUTHORIZED",
            hint=hint or default_hint,
        )


class ForbiddenError(APIError):
    """403 Forbidden."""

    def __init__(self, detail: str = "Forbidden", hint: str | None = None):
        super().__init__(status_code=403, detail=detail, code="FORBIDDEN", hint=hint)


class ConflictError(APIError):
    """409 Conflict."""

    def __init__(self, detail: str = "Conflict", hint: str | None = None):
        super().__init__(status_code=409, detail=detail, code="CONFLICT", hint=hint)


class NotFoundError(APIError):
    """404 Not Found."""

    def __init__(self, detail: str = "Resource not found", hint: str | None = None):
        super().__init__(status_code=404, detail=detail, code="NOT_FOUND", hint=hint)


class UnprocessableEntityError(APIError):
    """422 Unprocessable Entity."""

    def __init__(self, detail: str = "Validation error", hint: str | None = None):
        super().__init__(
            status_code=422, detail=detail, code="UNPROCESSABLE_ENTITY", hint=hint
        )


class ServiceUnavailableError(APIError):
    """503 Service Unavailable."""

    def __init__(self, detail: str = "Service unavailable", hint: str | None = None):
        super().__init__(
            status_code=503, detail=detail, code="SERVICE_UNAVAILABLE", hint=hint
        )


class ProviderConfigurationError(APIError):
    """500 Provider configuration error — replaces SystemExit in provider_factory."""

    def __init__(self, detail: str, hint: str | None = None):
        super().__init__(
            status_code=500, detail=detail, code="PROVIDER_CONFIG_ERROR", hint=hint
        )


def _status_to_code(status_code: int) -> str:
    """Convert an HTTP status code to a default error code string."""
    _MAP = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    return _MAP.get(status_code, f"ERROR_{status_code}")
