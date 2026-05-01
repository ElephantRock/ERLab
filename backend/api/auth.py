"""API key authentication dependency."""

from fastapi import Request

from backend.api.errors import UnauthorizedError
from backend.config import get_settings


async def verify_api_key(request: Request):
    settings = get_settings()
    if not settings.api_key:
        return  # auth disabled when key not set
    key = request.headers.get("X-API-Key", "")
    if key != settings.api_key:
        raise UnauthorizedError()
