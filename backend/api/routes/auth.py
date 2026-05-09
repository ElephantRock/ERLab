"""Auth routes — register, login, me, users (BATCH-28)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from backend.api.auth import (
    TokenData,
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from backend.api.errors import ConflictError, UnauthorizedError
from backend.db.database import get_session
from backend.db.models import User

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# ── Routes ─────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    """Create a new user account and return a JWT token."""
    with get_session() as session:
        # Check for existing username
        existing = session.query(User).filter(
            (User.username == body.username) | (User.email == body.email)
        ).first()
        if existing:
            field = "username" if existing.username == body.username else "email"
            raise ConflictError(
                detail=f"A user with this {field} already exists",
                hint="Choose a different username or email",
            )

        user = User(
            username=body.username,
            email=body.email,
            hashed_password=hash_password(body.password),
            role="user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        token = create_access_token({
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
        })

        return AuthResponse(
            token=token,
            user=UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                role=user.role,
            ),
        )


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest):
    """Authenticate a user and return a JWT token."""
    with get_session() as session:
        user = session.query(User).filter(User.username == body.username).first()
        if not user or not verify_password(body.password, user.hashed_password):
            raise UnauthorizedError(
                detail="Invalid username or password",
                hint="Check your credentials and try again",
            )

        token = create_access_token({
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
        })

        return AuthResponse(
            token=token,
            user=UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                role=user.role,
            ),
        )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: TokenData = Depends(get_current_user)):
    """Return the current authenticated user's info."""
    # Dev mode — return synthetic dev user when auth_enabled=False
    if current_user.user_id == 0:
        return UserResponse(
            id=0,
            username="dev",
            email="dev@localhost",
            role="admin",
        )
    with get_session() as session:
        user = session.query(User).filter(User.id == current_user.user_id).first()
        if not user:
            raise UnauthorizedError(detail="User not found")
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
        )


@router.post("/forgot-password", summary="Request password reset")
def forgot_password(body: ForgotPasswordRequest):
    """Request a password reset token.

    Always returns 200 to prevent email enumeration.
    In production, this would send an email with a reset link.
    In dev mode, the reset token is logged and returned.
    """
    import secrets
    import logging

    with get_session() as session:
        user = session.query(User).filter(User.email == body.email).first()
        if not user:
            # Don't reveal whether email exists — still return 200
            return {"message": "If an account with this email exists, a reset token has been sent."}

        # Generate a secure reset token
        reset_token = secrets.token_urlsafe(32)

        # Store token (in production: Redis with TTL, or email it)
        # For dev: store in user's hashed_password field temporarily
        # In production: send email with link containing token
        logger = logging.getLogger(__name__)
        logger.info(
            "Password reset requested for user=%s email=%s token=%s",
            user.username, user.email, reset_token,
        )

        # Store the reset token for verification
        user.hashed_password = f"RESET:{reset_token}:{hash_password(reset_token)}"
        session.commit()

        # In dev mode, return the token for testing
        from backend.config import get_settings
        settings = get_settings()
        if settings.debug:
            return {
                "message": "Reset token generated (debug mode).",
                "token": reset_token,
                "hint": "Use POST /auth/reset-password with this token.",
            }

        return {"message": "If an account with this email exists, a reset token has been sent."}


@router.post("/reset-password", summary="Reset password with token")
def reset_password(body: ResetPasswordRequest):
    """Reset password using a valid reset token.

    In production, the token would come from an email link.
    In dev mode, use the token returned by /forgot-password.
    """
    with get_session() as session:
        # Find user with matching reset token
        users = session.query(User).all()
        matched_user = None
        for user in users:
            if user.hashed_password.startswith(f"RESET:{body.token}:"):
                matched_user = user
                break

        if not matched_user:
            raise UnauthorizedError(
                detail="Invalid or expired reset token",
                hint="Request a new token via POST /auth/forgot-password",
            )

        # Set new password
        matched_user.hashed_password = hash_password(body.new_password)
        session.commit()

        return {"message": "Password has been reset successfully."}


@router.get("/users", response_model=list[UserResponse])
def list_users(current_user: TokenData = Depends(require_role("admin"))):
    """List all users. Admin only."""
    with get_session() as session:
        users = session.query(User).all()
        return [
            UserResponse(id=u.id, username=u.username, email=u.email, role=u.role)
            for u in users
        ]
