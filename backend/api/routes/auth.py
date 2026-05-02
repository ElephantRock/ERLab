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


@router.get("/users", response_model=list[UserResponse])
def list_users(current_user: TokenData = Depends(require_role("admin"))):
    """List all users. Admin only."""
    with get_session() as session:
        users = session.query(User).all()
        return [
            UserResponse(id=u.id, username=u.username, email=u.email, role=u.role)
            for u in users
        ]
