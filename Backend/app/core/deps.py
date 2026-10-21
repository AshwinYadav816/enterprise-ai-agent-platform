"""Request dependencies: authenticated user, role checks, client IP."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.db import DbSession
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.models import User, UserRole

_bearer = HTTPBearer(auto_error=False, description="Access token from /auth/login")
_CHALLENGE = {"WWW-Authenticate": "Bearer"}


def _unauthorized(code: str, message: str) -> AppError:
    return AppError(code, message, 401, _CHALLENGE)


async def _authenticated_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("not_authenticated", "Not authenticated")
    claims = decode_access_token(credentials.credentials)
    try:
        user_id = uuid.UUID(claims["sub"])
    except ValueError as exc:
        raise _unauthorized("invalid_token", "Invalid access token") from exc
    user = await db.get(User, user_id)
    if user is None or str(user.org_id) != claims["org"]:
        raise _unauthorized("invalid_token", "Invalid access token")
    if not user.is_active:
        raise AppError("account_disabled", "This account has been deactivated", 403)
    return user


async def get_current_user_allow_password_change(
    user: Annotated[User, Depends(_authenticated_user)],
) -> User:
    """For the few routes a user must reach before changing a temporary password."""
    return user


async def get_current_user(user: Annotated[User, Depends(_authenticated_user)]) -> User:
    if user.must_change_password:
        raise AppError(
            "password_change_required", "Please change your temporary password first", 403
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserAllowPasswordChange = Annotated[User, Depends(get_current_user_allow_password_change)]


def require_roles(*roles: UserRole) -> Callable[..., Awaitable[User]]:
    """Dependency factory: `Depends(require_roles(UserRole.admin))`."""
    allowed = set(roles)

    async def _check(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise AppError("forbidden", "You don't have permission to do this", 403)
        return user

    return _check


def client_ip(request: Request) -> str:
    """Peer address (behind a proxy, uvicorn --proxy-headers puts the real client here)."""
    return request.client.host if request.client else "unknown"


ClientIP = Annotated[str, Depends(client_ip)]
