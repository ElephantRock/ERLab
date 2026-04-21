"""API error hierarchy for proper HTTP status codes."""


class APIError(Exception):
    """Base API error with HTTP status code."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class NotFoundError(APIError):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=404, detail=detail)


class ServiceUnavailableError(APIError):
    def __init__(self, detail: str = "Service unavailable"):
        super().__init__(status_code=503, detail=detail)
