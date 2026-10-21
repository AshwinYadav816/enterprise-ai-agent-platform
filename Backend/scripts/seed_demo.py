"""Create (or reset) the demo organization and its users for the viva/demo.

    uv run python scripts/seed_demo.py

Idempotent: re-running resets the three demo users to the known passwords below and
re-activates them. Uses DATABASE_URL from .env. Never run against production.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.db import get_engine, get_sessionmaker  # noqa: E402
from app.core.security import hash_password_async  # noqa: E402
from app.models import Organization, User, UserRole  # noqa: E402

ORG_NAME = "Acme Demo"
DEMO_USERS = [
    ("admin@acme-demo.com", "Asha Admin", UserRole.admin, "Admin@Demo2026"),
    ("manager@acme-demo.com", "Manish Manager", UserRole.manager, "Manager@Demo2026"),
    ("employee@acme-demo.com", "Esha Employee", UserRole.employee, "Employee@Demo2026"),
]


async def seed() -> None:
    async with get_sessionmaker()() as db:
        admin_email = DEMO_USERS[0][0]
        existing = await db.scalar(select(User).where(User.email == admin_email))
        if existing is not None:
            org = await db.get(Organization, existing.org_id)
        else:
            org = Organization(name=ORG_NAME)
            db.add(org)
            await db.flush()
        assert org is not None

        for email, name, role, password in DEMO_USERS:
            user = await db.scalar(select(User).where(User.email == email))
            if user is not None and user.org_id != org.id:
                raise SystemExit(f"{email} already belongs to another organization; aborting.")
            if user is None:
                user = User(org_id=org.id, email=email)
                db.add(user)
            user.full_name, user.role = name, role
            user.password_hash = await hash_password_async(password)
            user.is_active, user.must_change_password = True, False
        await db.commit()

    print(f"Demo organization: {ORG_NAME}")
    print(f"{'role':10} {'email':26} password")
    for email, _, role, password in DEMO_USERS:
        print(f"{role.value:10} {email:26} {password}")
    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(seed())
