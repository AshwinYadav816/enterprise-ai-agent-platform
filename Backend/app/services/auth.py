"""Registration, login, refresh-token rotation, logout, password change."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.models import Organization, RefreshToken, User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services import audit

log = logging.getLogger(__name__)


def _invalid_credentials() -> AppError:
    # Same message for unknown email and wrong password: don't reveal which emails exist.
    return AppError("invalid_credentials", "Invalid email or password", 401)


def _invalid_refresh() -> AppError:
    return AppError("invalid_refresh_token", "Session expired. Please log in again.", 401)


@dataclass
class Session:
    user: User
    access_token: str
    expires_in: int
    refresh_token: str  # raw value, goes into the httpOnly cookie only


def _now() -> datetime:
    return datetime.now(UTC)


async def issue_session(db: AsyncSession, user: User) -> Session:
    raw, token_hash = new_refresh_token()
    days = get_settings().refresh_token_days
    db.add(
        RefreshToken(
            user_id=user.id, token_hash=token_hash, expires_at=_now() + timedelta(days=days)
        )
    )
    await db.flush()
    access, expires_in = create_access_token(user)
    return Session(user, access, expires_in, raw)


async def revoke_all(db: AsyncSession, user_id: object) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


async def register(db: AsyncSession, data: RegisterRequest, ip: str | None = None) -> Session:
    if await db.scalar(select(User.id).where(User.email == data.email)):
        raise AppError("email_taken", "An account with this email already exists", 409)
    org = Organization(name=data.org_name.strip())
    db.add(org)
    await db.flush()
    user = User(
        org_id=org.id,
        email=data.email,
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.password),
        role=UserRole.admin,
        last_login_at=_now(),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    await audit.log(
        db,
        org_id=org.id,
        user_id=user.id,
        action=audit.REGISTER,
        meta={"org_name": org.name},
        ip=ip,
    )
    return await issue_session(db, user)


async def login(db: AsyncSession, data: LoginRequest, ip: str | None = None) -> Session:
    user = await db.scalar(select(User).where(User.email == data.email))
    valid, new_hash = verify_password(data.password, user.password_hash if user else None)
    if user is None:
        # No org to attach an audit row to (org_id is required): app log only.
        log.info("Login failed for unknown email from %s", ip)
        raise _invalid_credentials()
    if not valid:
        await audit.log(
            db,
            org_id=user.org_id,
            user_id=None,
            action=audit.LOGIN_FAILED,
            target_type="user",
            target_id=user.id,
            meta={"email": data.email},
            ip=ip,
        )
        await db.commit()  # keep the audit row: the error below makes get_db roll back
        raise _invalid_credentials()
    if not user.is_active:
        raise AppError("account_disabled", "This account has been deactivated", 403)
    if new_hash:  # hashing parameters were upgraded since this password was set
        user.password_hash = new_hash
    user.last_login_at = _now()
    await audit.log(db, org_id=user.org_id, user_id=user.id, action=audit.LOGIN, ip=ip)
    return await issue_session(db, user)


async def refresh(db: AsyncSession, raw_token: str | None) -> Session:
    """Rotate: the presented token is revoked and a new one issued.

    Presenting an already-revoked token means it was stolen or replayed, so every session of
    that user is revoked. That revocation is committed before raising, because the request
    session rolls back on errors.
    """
    if not raw_token:
        raise _invalid_refresh()
    token = await db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(raw_token))
        .with_for_update()
    )
    if token is None:
        raise _invalid_refresh()
    if token.revoked_at is not None:
        log.warning(
            "Refresh token reuse detected for user %s; revoking all sessions", token.user_id
        )
        await revoke_all(db, token.user_id)
        if owner := await db.get(User, token.user_id):
            await audit.log(
                db,
                org_id=owner.org_id,
                user_id=owner.id,
                action=audit.REFRESH_REUSE,
                meta={"all_sessions_revoked": True},
            )
        await db.commit()
        raise _invalid_refresh()
    if token.expires_at <= _now():
        raise _invalid_refresh()

    user = await db.get(User, token.user_id)
    token.revoked_at = _now()
    if user is None or not user.is_active:
        await db.commit()
        raise _invalid_refresh()
    return await issue_session(db, user)


async def logout(db: AsyncSession, raw_token: str | None) -> None:
    """Idempotent: unknown or already-revoked tokens are fine."""
    if not raw_token:
        return
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_refresh_token(raw_token),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=_now())
    )


async def change_password(
    db: AsyncSession, user: User, current: str, new: str, ip: str | None = None
) -> Session:
    """Revokes every session (the refresh cookie isn't sent to this path, so the current one
    can't be singled out) and returns a fresh session for the caller."""
    valid, _ = verify_password(current, user.password_hash)
    if not valid:
        raise AppError("invalid_password", "Current password is incorrect", 400)
    if verify_password(new, user.password_hash)[0]:
        raise AppError("password_reused", "New password must differ from the current one", 400)
    user.password_hash = hash_password(new)
    user.must_change_password = False
    await revoke_all(db, user.id)
    await audit.log(db, org_id=user.org_id, user_id=user.id, action=audit.PASSWORD_CHANGED, ip=ip)
    return await issue_session(db, user)
