"""Admin-only: user management, activity log, dashboard stats."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.db import DbSession
from app.core.deps import ClientIP, require_roles
from app.core.pagination import DEFAULT_LIMIT, CursorParam, LimitParam, Page
from app.models import User, UserRole
from app.schemas.admin import (
    AdminStats,
    AuditLogOut,
    CreatedUserResponse,
    CreateUserRequest,
    UpdateUserRequest,
)
from app.schemas.users import UserOut
from app.services import stats as stats_service
from app.services import users as users_service

router = APIRouter(prefix="/admin", tags=["admin"])

Admin = Annotated[User, Depends(require_roles(UserRole.admin))]


@router.get("/users")
async def list_users(
    admin: Admin,
    db: DbSession,
    search: Annotated[str | None, Query(max_length=200, description="email or name")] = None,
    role: UserRole | None = None,
    cursor: CursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> Page[UserOut]:
    rows, next_cursor = await users_service.list_users(
        db, admin.org_id, search=search, role=role, cursor=cursor, limit=limit
    )
    return Page(items=[UserOut.model_validate(u) for u in rows], next_cursor=next_cursor)


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    data: CreateUserRequest, admin: Admin, db: DbSession, ip: ClientIP
) -> CreatedUserResponse:
    """Create a user with a temporary password (returned only in this response)."""
    user, temp = await users_service.create_user(db, admin, data, ip)
    return CreatedUserResponse(user=UserOut.model_validate(user), temporary_password=temp)


@router.patch("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID, data: UpdateUserRequest, admin: Admin, db: DbSession, ip: ClientIP
) -> UserOut:
    """Change role and/or activate/deactivate (deactivating signs the user out everywhere)."""
    user = await users_service.update_user(db, admin, user_id, data, ip)
    return UserOut.model_validate(user)


@router.get("/activity")
async def list_activity(
    admin: Admin,
    db: DbSession,
    action: Annotated[str | None, Query(max_length=100, examples=["auth.login"])] = None,
    user_id: uuid.UUID | None = None,
    cursor: CursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> Page[AuditLogOut]:
    rows, next_cursor = await users_service.list_activity(
        db, admin.org_id, action=action, user_id=user_id, cursor=cursor, limit=limit
    )
    items = [
        AuditLogOut.model_validate(log).model_copy(update={"user_email": email})
        for log, email in rows
    ]
    return Page(items=items, next_cursor=next_cursor)


@router.get("/stats")
async def dashboard_stats(
    admin: Admin, db: DbSession, cache: stats_service.StatsCache
) -> AdminStats:
    """Everything the admin dashboard charts need, for your organization (cached 60 s)."""
    return await stats_service.get_stats(db, cache, admin.org_id)
