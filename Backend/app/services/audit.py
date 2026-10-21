"""Activity log for the admin dashboard. Rows join the caller's transaction."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog

# Action names (stable strings: the admin UI filters on them)
REGISTER = "auth.register"
LOGIN = "auth.login"
LOGIN_FAILED = "auth.login_failed"
REFRESH_REUSE = "auth.refresh_token_reuse"
PASSWORD_CHANGED = "user.password_changed"
USER_CREATED = "user.created"
ROLE_CHANGED = "user.role_changed"
USER_DEACTIVATED = "user.deactivated"
USER_REACTIVATED = "user.reactivated"
DOCUMENT_UPLOADED = "document.uploaded"
DOCUMENT_DELETED = "document.deleted"


async def log(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Add an audit row in the current transaction (committed or rolled back with it)."""
    db.add(
        AuditLog(
            org_id=org_id,
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            meta=meta,
            ip=ip,
        )
    )
