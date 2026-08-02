"""Authentication — API key + JWT token support (BATCH-28)."""

from datetime import datetime, timedelta, timezone

from fastapi import Depends, Request
from passlib.context import CryptContext
from pydantic import BaseModel

from backend.api.errors import ForbiddenError, UnauthorizedError
from backend.config import get_settings

# ── Password Hashing ───────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt. Truncates to 72 bytes (bcrypt limit)."""
    # bcrypt has a 72-byte password limit. Passlib with newer bcrypt
    # versions enforces this strictly. Truncate to avoid ValueError.
    password = password[:72]
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT Token ──────────────────────────────────────────────────────

def create_access_token(data: dict) -> str:
    from jose import jwt

    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    from jose import JWTError, jwt

    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        raise UnauthorizedError(detail="Invalid or expired token", hint="Log in again to get a new token")


# ── Schemas ────────────────────────────────────────────────────────

class TokenData(BaseModel):
    user_id: int | None = None
    username: str | None = None
    role: str | None = None


# ── FastAPI Dependencies ───────────────────────────────────────────

async def verify_api_key(request: Request):
    """Legacy API key authentication."""
    settings = get_settings()
    if not settings.api_key:
        return  # auth disabled when key not set
    key = request.headers.get("X-API-Key", "")
    if key != settings.api_key:
        raise UnauthorizedError()


async def get_current_user(request: Request) -> TokenData:
    """Extract and validate JWT token from Authorization header.

    When auth_enabled=False (dev mode), returns a default dev user.
    """
    settings = get_settings()

    # Dev mode — no auth required
    if not settings.auth_enabled:
        return TokenData(user_id=0, username="dev", role="admin")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise UnauthorizedError(detail="Missing authentication token", hint="Provide a Bearer token via the Authorization header")

    token = auth_header[7:]
    payload = decode_access_token(token)

    user_id = payload.get("sub")
    username = payload.get("username")
    role = payload.get("role")

    if user_id is None:
        raise UnauthorizedError(detail="Invalid token payload")

    return TokenData(user_id=int(user_id), username=username, role=role)


def require_role(*roles: str):
    """Dependency factory: raises 403 if the current user lacks the required role."""
    async def _check(user: TokenData = Depends(get_current_user)) -> TokenData:
        if user.role not in roles:
            raise ForbiddenError(detail=f"Role '{user.role}' not allowed. Required: {', '.join(roles)}")
        return user
    return _check
