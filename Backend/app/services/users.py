"""Admin user management, scoped to the admin's organization."""

import secrets
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.pagination import next_cursor_for, paginate
from app.core.security import hash_password_async
from app.models import AuditLog, User, UserRole
from app.schemas.admin import CreateUserRequest, UpdateUserRequest
from app.services import audit
from app.services.auth import revoke_all

# No look-alike characters (0/O, 1/l/I) so temporary passwords can be read out loud or typed.
_TEMP_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TEMP_PASSWORD_LENGTH = 14


def generate_temporary_password() -> str:
    return "".join(secrets.choice(_TEMP_ALPHABET) for _ in range(TEMP_PASSWORD_LENGTH))


def _not_found() -> AppError:
    return AppError("not_found", "User not found", 404)


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def list_users(
    db: AsyncSession,
    org_id: uuid.UUID,
    *,
    search: str | None,
    role: UserRole | None,
    cursor: str | None,
    limit: int,
) -> tuple[list[User], str | None]:
    stmt = select(User).where(User.org_id == org_id)
    if search and (term := search.strip()):
        pattern = f"%{_escape_like(term)}%"
        stmt = stmt.where(
            or_(User.email.ilike(pattern, escape="\\"), User.full_name.ilike(pattern, escape="\\"))
        )
    if role:
        stmt = stmt.where(User.role == role)
    rows = list((await db.scalars(paginate(stmt, User.created_at, User.id, cursor, limit))).all())
    return rows, next_cursor_for(rows, limit)


async def create_user(
    db: AsyncSession, admin: User, data: CreateUserRequest, ip: str | None
) -> tuple[User, str]:
    if await db.scalar(select(User.id).where(User.email == data.email)):
        raise AppError("email_taken", "An account with this email already exists", 409)
    temp = generate_temporary_password()
    user = User(
        org_id=admin.org_id,
        email=data.email,
        full_name=data.full_name.strip(),
        role=data.role,
        password_hash=await hash_password_async(temp),
        must_change_password=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    await audit.log(
        db,
        org_id=admin.org_id,
        user_id=admin.id,
        action=audit.USER_CREATED,
        target_type="user",
        target_id=user.id,
        meta={"email": user.email, "role": user.role.value},
        ip=ip,
    )
    return user, temp


async def _ensure_another_active_admin(
    db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Refuse to leave the org without an active admin.

    Locks the org's active admin rows, so two admins demoting each other at the same moment
    can't both succeed and leave zero admins.
    """
    admins = await db.scalars(
        select(User.id)
        .where(User.org_id == org_id, User.role == UserRole.admin, User.is_active.is_(True))
        .with_for_update()
    )
    if not [a for a in admins if a != user_id]:
        raise AppError("last_admin", "The organization must keep at least one active admin", 409)


async def update_user(
    db: AsyncSession, admin: User, user_id: uuid.UUID, data: UpdateUserRequest, ip: str | None
) -> User:
    user = await db.scalar(select(User).where(User.id == user_id, User.org_id == admin.org_id))
    if user is None:  # other orgs' users are indistinguishable from missing ones
        raise _not_found()

    demoting = data.role is not None and data.role != UserRole.admin
    deactivating = data.is_active is False
    if user.id == admin.id and (demoting or deactivating):
        raise AppError("cannot_modify_self", "You can't demote or deactivate your own account", 400)
    if user.role == UserRole.admin and user.is_active and (demoting or deactivating):
        await _ensure_another_active_admin(db, admin.org_id, user.id)

    if data.role is not None and data.role != user.role:
        await audit.log(
            db,
            org_id=admin.org_id,
            user_id=admin.id,
            action=audit.ROLE_CHANGED,
            target_type="user",
            target_id=user.id,
            meta={"from": user.role.value, "to": data.role.value},
            ip=ip,
        )
        user.role = data.role
    if data.is_active is not None and data.is_active != user.is_active:
        user.is_active = data.is_active
        if not data.is_active:
            await revoke_all(db, user.id)  # sign them out everywhere
        await audit.log(
            db,
            org_id=admin.org_id,
            user_id=admin.id,
            action=audit.USER_DEACTIVATED if not data.is_active else audit.USER_REACTIVATED,
            target_type="user",
            target_id=user.id,
            ip=ip,
        )
    await db.flush()
    return user


async def list_activity(
    db: AsyncSession,
    org_id: uuid.UUID,
    *,
    action: str | None,
    user_id: uuid.UUID | None,
    cursor: str | None,
    limit: int,
) -> tuple[list[tuple[AuditLog, str | None]], str | None]:
    stmt = (
        select(AuditLog, User.email)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(AuditLog.org_id == org_id)
    )
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    result = await db.execute(paginate(stmt, AuditLog.created_at, AuditLog.id, cursor, limit))
    rows: list[tuple[AuditLog, str | None]] = [(log, email) for log, email in result.all()]
    return rows, next_cursor_for(rows, limit, key=lambda row: row[0])
