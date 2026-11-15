"""
FastAPI dependencies — DB session, current user, role enforcement.

Usage in routes:
    def list_leads(db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
        ...

    @router.delete("/admin/seed")
    def reseed(user: User = Depends(require_role("admin"))):
        ...
"""
from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from backend.app.core.security import decode_token
from backend.app.database import SessionLocal
from backend.app.models.system import User


_bearer = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Extract + validate the JWT. Returns the ORM User."""
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(creds.credentials)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing subject")

    user = db.query(User).filter(User.business_id == sub).one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_role(*role_names: str):
    """Factory — returns a dependency that requires ANY of the given roles."""
    allowed = set(role_names)

    def _checker(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        role_value = user.role.name.value if user.role else None
        if role_value not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {sorted(allowed)}",
            )
        return user

    return _checker
