"""
Auth endpoints — login + refresh.

POST /api/auth/login   {email, password} → {access_token, token_type, user}
GET  /api/auth/me      (Bearer) → user
POST /api/auth/refresh (Bearer) → new token

Demo: seeded users have placeholder password hashes; the first successful
login lazily upgrades the hash to a real bcrypt hash.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db
from backend.app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from backend.app.models.system import User


router = APIRouter(prefix="/api/auth", tags=["auth"])

DEMO_PASSWORD = "leadflow-demo"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    business_id: str
    email: str
    full_name: str
    role: str

    @classmethod
    def from_user(cls, u: User) -> "UserOut":
        return cls(
            business_id=u.business_id,
            email=u.email,
            full_name=u.full_name,
            role=u.role.name.value if u.role else "unknown",
        )


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(User).filter(User.email == body.email).one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User inactive")

    ok = verify_password(body.password, user.hashed_password)

    # Demo shortcut — seed uses a placeholder hash
    if not ok and user.hashed_password.startswith("$2b$12$demo"):
        if body.password == DEMO_PASSWORD:
            user.hashed_password = hash_password(body.password)
            user.last_login_at = datetime.now(timezone.utc)
            db.commit()
            ok = True

    if not ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    role_name = user.role.name.value if user.role else None
    token = create_access_token(subject=user.business_id, roles=[role_name] if role_name else [])
    return LoginResponse(access_token=token, user=UserOut.from_user(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.from_user(user)


@router.post("/refresh", response_model=LoginResponse)
def refresh(user: User = Depends(get_current_user)) -> LoginResponse:
    role_name = user.role.name.value if user.role else None
    token = create_access_token(subject=user.business_id, roles=[role_name] if role_name else [])
    return LoginResponse(access_token=token, user=UserOut.from_user(user))
