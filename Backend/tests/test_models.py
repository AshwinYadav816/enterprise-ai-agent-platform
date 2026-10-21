import uuid
from typing import Any

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core import db as db_module
from app.models import (
    Base,
    Conversation,
    Document,
    DocumentStatus,
    Message,
    MessageRole,
    MessageStatus,
    RefreshToken,
    User,
    UserRole,
)
from tests.factories import make_org, make_user


async def test_create_org_and_user_with_defaults(db: AsyncSession) -> None:
    org = await make_org(db, "Globex")
    user = await make_user(db, org, role=UserRole.manager, email="ana@globex.com")
    assert isinstance(org.id, uuid.UUID) and org.created_at is not None
    assert user.org_id == org.id and user.role is UserRole.manager
    assert user.is_active is True and user.must_change_password is False
    assert user.last_login_at is None
    stored = await db.scalar(text("SELECT role::text FROM users WHERE id = :id"), {"id": user.id})
    assert stored == "manager"  # enum stored by value


async def test_unique_email_violation(db: AsyncSession) -> None:
    org = await make_org(db)
    await make_user(db, org, email="dup@example.com")
    with pytest.raises(IntegrityError, match="uq_users_email"):
        async with db.begin_nested():
            await make_user(db, org, email="dup@example.com")
    count = await db.scalar(select(func.count()).where(User.email == "dup@example.com"))
    assert count == 1  # the session is still usable after the failed savepoint


async def test_email_must_be_lowercase(db: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_users_email_lowercase"):
        async with db.begin_nested():
            await make_user(db, email="Mixed@Example.com")


async def test_delete_conversation_cascades_to_messages(db: AsyncSession) -> None:
    user = await make_user(db)
    conv = Conversation(org_id=user.org_id, user_id=user.id, title="Leave questions")
    db.add(conv)
    await db.flush()
    db.add_all(
        [
            Message(conversation_id=conv.id, role=MessageRole.user, content="How many days?"),
            Message(conversation_id=conv.id, role=MessageRole.assistant, content="24 days [1]"),
        ]
    )
    await db.flush()
    msg_count = select(func.count()).select_from(Message).where(Message.conversation_id == conv.id)
    assert await db.scalar(msg_count) == 2
    first = await db.scalar(select(Message).where(Message.conversation_id == conv.id).limit(1))
    assert first is not None and first.status is MessageStatus.complete
    assert first.prompt_tokens == 0 and first.completion_tokens == 0

    await db.delete(conv)
    await db.flush()
    assert await db.scalar(msg_count) == 0  # ON DELETE CASCADE in Postgres


async def test_delete_user_cascades_refresh_tokens(db: AsyncSession) -> None:
    user = await make_user(db)
    db.add(RefreshToken(user_id=user.id, token_hash="a" * 64, expires_at=user.created_at))
    await db.flush()
    await db.delete(user)
    await db.flush()
    remaining = await db.scalar(select(func.count()).select_from(RefreshToken))
    assert remaining == 0


async def test_document_defaults_and_visibility_overlap(db: AsyncSession) -> None:
    user = await make_user(db, role=UserRole.manager)
    for name, roles in (("handbook.pdf", ["employee"]), ("budget.xlsx", ["manager"])):
        db.add(
            Document(
                org_id=user.org_id,
                owner_id=user.id,
                filename=name,
                content_type="application/octet-stream",
                size_bytes=1024,
                storage_key=f"{user.org_id}/x/{name}",
                allowed_roles=roles,
            )
        )
    await db.flush()

    def visible_to(roles: list[str]) -> Any:
        return select(Document.filename).where(
            Document.org_id == user.org_id, Document.allowed_roles.overlap(roles)
        )

    assert set(await db.scalars(visible_to(["employee"]))) == {"handbook.pdf"}
    assert set(await db.scalars(visible_to(["manager", "employee"]))) == {
        "handbook.pdf",
        "budget.xlsx",
    }
    doc = await db.scalar(select(Document).where(Document.filename == "handbook.pdf"))
    assert doc is not None
    await db.refresh(doc)
    assert doc.status is DocumentStatus.processing and doc.warnings == []
    assert doc.updated_at is not None and doc.chunk_count is None


async def test_migrations_match_models(db_engine: AsyncEngine) -> None:
    """Fails if a model changed without a new Alembic migration."""
    async with db_engine.connect() as conn:
        diff = await conn.run_sync(
            lambda sync_conn: compare_metadata(
                MigrationContext.configure(
                    sync_conn, opts={"compare_type": True, "compare_server_default": True}
                ),
                Base.metadata,
            )
        )
    assert diff == []


class FakeSession:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.events.append("close")

    async def commit(self) -> None:
        self.events.append("commit")

    async def rollback(self) -> None:
        self.events.append("rollback")


async def test_get_db_commits_on_success_and_rolls_back_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    monkeypatch.setattr(db_module, "get_sessionmaker", lambda: lambda: session)

    gen = db_module.get_db()
    assert await anext(gen) is session
    with pytest.raises(StopAsyncIteration):
        await anext(gen)
    assert session.events == ["commit", "close"]

    session.events.clear()
    gen = db_module.get_db()
    await anext(gen)
    with pytest.raises(ValueError):
        await gen.athrow(ValueError("handler failed"))
    assert session.events == ["rollback", "close"]
