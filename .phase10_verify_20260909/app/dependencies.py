from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.access_control import can_access_department
from app.utils.jwt import decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.get("userId"))
    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.query(User).filter(User.userId == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.status != "Approved":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not approved")
    return user


def require_approved_user(user: User = Depends(get_current_user)) -> User:
    return user


def require_admin(user: User = Depends(require_approved_user)) -> User:
    if not user.role or user.role.roleName != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def require_operator_or_admin(user: User = Depends(require_approved_user)) -> User:
    role_name = user.role.roleName if user.role else ""
    if role_name not in {"Admin", "User"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator or admin access required")
    return user


def require_department_access(departmentId: int) -> Callable[[User], User]:
    def dependency(user: User = Depends(require_operator_or_admin)) -> User:
        if not can_access_department(user, departmentId):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
        return user

    return dependency
