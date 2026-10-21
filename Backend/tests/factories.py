"""Small async factories for test data. They flush (so ids/defaults exist) but don't commit."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, User, UserRole


async def make_org(db: AsyncSession, name: str = "Acme Corp") -> Organization:
    org = Organization(name=name)
    db.add(org)
    await db.flush()
    return org


async def make_user(
    db: AsyncSession,
    org: Organization | None = None,
    *,
    role: UserRole = UserRole.employee,
    email: str | None = None,
    full_name: str = "Test User",
    password_hash: str = "not-a-real-hash",
    is_active: bool = True,
) -> User:
    org = org or await make_org(db)
    user = User(
        org_id=org.id,
        email=email or f"user-{uuid.uuid4().hex[:8]}@example.com",
        full_name=full_name,
        password_hash=password_hash,
        role=role,
        is_active=is_active,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)  # load server defaults (created_at, must_change_password, ...)
    return user
