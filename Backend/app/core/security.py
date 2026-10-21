"""Password hashing, JWT access tokens, refresh-token generation, role hierarchy."""

import asyncio
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import User, UserRole

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"

_hasher = PasswordHash((Argon2Hasher(),))
# Verified against when the email doesn't exist, so response time doesn't reveal valid emails.
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")


# --- passwords ----------------------------------------------------------------------------


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> tuple[bool, str | None]:
    """(valid, new_hash): new_hash is set when the stored hash should be upgraded."""
    if password_hash is None:
        _hasher.verify(password, _DUMMY_HASH)
        return False, None
    return _hasher.verify_and_update(password, password_hash)


# Argon2 costs ~65 ms of CPU per call (by design). Run it in a worker thread so one login
# doesn't freeze every other request on the event loop (e.g. live chat streams).


async def hash_password_async(password: str) -> str:
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(
    password: str, password_hash: str | None
) -> tuple[bool, str | None]:
    return await asyncio.to_thread(verify_password, password, password_hash)


# --- access tokens (JWT) ------------------------------------------------------------------------


def create_access_token(user: User) -> tuple[str, int]:
    """(token, expires_in_seconds)."""
    s = get_settings()
    now = datetime.now(UTC)
    ttl = timedelta(minutes=s.access_token_minutes)
    claims = {
        "sub": str(user.id),
        "org": str(user.org_id),
        "role": user.role.value,
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + ttl,
    }
    token = jwt.encode(claims, s.jwt_secret.get_secret_value(), algorithm=JWT_ALGORITHM)
    return token, int(ttl.total_seconds())


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "org", "role", "type", "exp", "iat"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AppError("token_expired", "Access token expired", 401, _BEARER) from exc
    except jwt.PyJWTError as exc:
        raise AppError("invalid_token", "Invalid access token", 401, _BEARER) from exc
    if claims.get("type") != ACCESS_TOKEN_TYPE:
        raise AppError("invalid_token", "Invalid access token", 401, _BEARER)
    return claims


_BEARER = {"WWW-Authenticate": "Bearer"}


# --- refresh tokens (opaque, only the hash is stored) ---------------------------------------------


def new_refresh_token() -> tuple[str, str]:
    """(raw token for the cookie, sha256 hex to store)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# --- roles ---------------------------------------------------------------------------------------

_ROLE_RANK = {UserRole.employee: 0, UserRole.manager: 1, UserRole.admin: 2}


def expand_roles(role: UserRole | str) -> list[str]:
    """Roles whose content `role` may see: admin ⊇ manager ⊇ employee.

    Used for API permissions and document visibility (Postgres `&&` and the AI module's filter).
    """
    rank = _ROLE_RANK[UserRole(role)]
    return [r.value for r, r_rank in _ROLE_RANK.items() if r_rank <= rank]
