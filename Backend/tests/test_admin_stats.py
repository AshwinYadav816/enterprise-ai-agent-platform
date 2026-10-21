import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import (
    Conversation,
    Document,
    DocumentStatus,
    Generation,
    GenerationKind,
    Message,
    MessageRole,
    Organization,
    UserRole,
)
from app.services.stats import CACHE_TTL_SECONDS, compute, get_stats_cache
from tests.conftest import FakeRedis
from tests.factories import make_org, make_user

API = "/api/v1"
PASSWORD = "correct-horse-battery"
NOW = datetime.now(UTC)


def ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


async def seed(db: AsyncSession, org: Organization, scale: int = 1) -> None:
    """Known data; `scale` lets a second org have different numbers."""
    admin = await make_user(db, org, role=UserRole.admin, password=PASSWORD)
    admin.last_login_at = ago(1)
    manager = await make_user(db, org, role=UserRole.manager)
    manager.last_login_at = ago(10)  # not active in the last 7 days
    await make_user(db, org, role=UserRole.employee, is_active=False)  # deactivated

    for status, size in (
        (DocumentStatus.ready, 100),
        (DocumentStatus.ready, 200),
        (DocumentStatus.failed, 50),
    ):
        db.add(
            Document(
                org_id=org.id,
                owner_id=admin.id,
                filename="f.pdf",
                content_type="application/pdf",
                size_bytes=size * scale,
                storage_key=f"{org.id}/{uuid.uuid4()}/f.pdf",
                allowed_roles=["employee"],
                status=status,
            )
        )

    conv = Conversation(org_id=org.id, user_id=admin.id)
    db.add_all([conv, Conversation(org_id=org.id, user_id=manager.id)])
    await db.flush()

    def msg(role: MessageRole, agent: str | None, p: int, c: int, days: float) -> Message:
        return Message(
            conversation_id=conv.id,
            role=role,
            content="x",
            agent=agent,
            prompt_tokens=p * scale,
            completion_tokens=c * scale,
            created_at=ago(days),
        )

    db.add_all(
        [
            msg(MessageRole.user, None, 0, 0, 0),
            msg(MessageRole.assistant, "research", 100, 20, 0),
            msg(MessageRole.assistant, "meeting,email", 60, 20, 3),  # tokens split 40/40
            msg(MessageRole.assistant, "research", 500, 500, 40),  # outside the 30-day window
        ]
    )

    def gen(kind: GenerationKind, p: int, c: int, days: float) -> Generation:
        return Generation(
            org_id=org.id,
            user_id=admin.id,
            kind=kind,
            title="t",
            input={},
            output={},
            prompt_tokens=p * scale,
            completion_tokens=c * scale,
            created_at=ago(days),
        )

    db.add_all(
        [
            gen(GenerationKind.meeting, 30, 10, 0),
            gen(GenerationKind.report, 5, 5, 2),
            gen(GenerationKind.document_insights, 10, 0, 1),
        ]
    )
    await db.flush()


async def two_orgs(db: AsyncSession) -> tuple[Organization, Organization]:
    a, b = await make_org(db, "Acme"), await make_org(db, "Globex")
    await seed(db, a)
    await seed(db, b, scale=7)  # different numbers that must never leak into Acme's
    return a, b


# --- numbers --------------------------------------------------------------------------------


async def test_stats_numbers_on_seeded_data(db: AsyncSession) -> None:
    acme, _ = await two_orgs(db)
    s = await compute(db, acme.id, now=NOW)

    assert s.users.model_dump() == {
        "total": 3,
        "by_role": {"admin": 1, "manager": 1, "employee": 1},
        "active_last_7_days": 1,
        "deactivated": 1,
    }
    assert s.documents.model_dump() == {
        "total": 3,
        "by_status": {"processing": 0, "ready": 2, "failed": 1},
        "storage_bytes": 350,
    }
    assert s.conversations.total == 2 and s.messages.total == 4
    assert s.generations.by_kind == {"meeting": 1, "report": 1, "email": 0, "document_insights": 1}
    assert s.generations.total == 3

    days = {d.date: d for d in s.tokens.per_day}
    assert len(s.tokens.per_day) == 30 and s.tokens.per_day[-1].date == NOW.date()
    assert s.tokens.per_day[0].date == (NOW - timedelta(days=29)).date()
    today = days[NOW.date()]
    assert (today.prompt_tokens, today.completion_tokens) == (
        130,
        30,
    )  # chat 100/20 + meeting 30/10
    assert days[ago(1).date()].total_tokens == 10  # insights
    assert days[ago(2).date()].total_tokens == 10  # report
    assert days[ago(3).date()].total_tokens == 80  # multi-agent reply
    assert (
        len([d for d in s.tokens.per_day if d.total_tokens]) == 4
    )  # every other day filled with 0
    assert s.tokens.last_30_days_total == 160 + 10 + 10 + 80  # the 40-day-old 1000 excluded

    per_agent = {u.agent: (u.requests, u.tokens) for u in s.tokens.per_agent}
    assert per_agent == {
        "research": (1, 120),
        "meeting": (2, 80),  # reply share 40 + meeting tool 40
        "email": (1, 40),
        "report": (1, 10),
        "document": (1, 10),
    }
    assert sum(t for _, t in per_agent.values()) == s.tokens.last_30_days_total  # no double count
    assert [u.agent for u in s.tokens.per_agent][:2] == ["research", "meeting"]  # most tokens first


async def test_empty_org_has_all_keys_and_30_zero_days(db: AsyncSession) -> None:
    org = await make_org(db)
    s = await compute(db, org.id, now=NOW)
    assert s.users.by_role == {"admin": 0, "manager": 0, "employee": 0}
    assert s.documents.by_status == {"processing": 0, "ready": 0, "failed": 0}
    assert len(s.tokens.per_day) == 30 and s.tokens.last_30_days_total == 0
    assert s.tokens.per_agent == []


async def test_uses_six_aggregate_queries(db: AsyncSession, db_engine: AsyncEngine) -> None:
    acme, _ = await two_orgs(db)
    statements: list[str] = []

    def count(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    event.listen(db_engine.sync_engine, "before_cursor_execute", count)
    try:
        await compute(db, acme.id, now=NOW)
    finally:
        event.remove(db_engine.sync_engine, "before_cursor_execute", count)
    assert len(statements) == 6
    assert all("count(" in s.lower() or "sum(" in s.lower() for s in statements)  # aggregates only


# --- API: access + cache ---------------------------------------------------------------------


async def admin_headers(
    client: httpx.AsyncClient, db: AsyncSession, role: UserRole
) -> tuple[Organization, dict[str, str]]:
    org = await make_org(db)
    user = await make_user(db, org, role=role, password=PASSWORD)
    r = await client.post(f"{API}/auth/login", json={"email": user.email, "password": PASSWORD})
    return org, {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.parametrize("role", [UserRole.manager, UserRole.employee])
async def test_non_admin_gets_403(
    client: httpx.AsyncClient, db: AsyncSession, role: UserRole
) -> None:
    _, h = await admin_headers(client, db, role)
    assert (await client.get(f"{API}/admin/stats", headers=h)).status_code == 403


async def test_endpoint_caches_per_org_for_60s(
    client: httpx.AsyncClient, db: AsyncSession, fake_redis: FakeRedis
) -> None:
    org, h = await admin_headers(client, db, UserRole.admin)
    first = await client.get(f"{API}/admin/stats", headers=h)
    assert first.status_code == 200
    assert first.json()["users"]["by_role"]["admin"] == 1
    key = f"stats:{org.id}"
    assert key in fake_redis.values and fake_redis.ttls[key] == CACHE_TTL_SECONDS

    await make_user(db, org)  # new data within the cache window
    cached = await client.get(f"{API}/admin/stats", headers=h)
    assert cached.json() == first.json()

    fake_redis.values.clear()  # cache expired
    fresh = await client.get(f"{API}/admin/stats", headers=h)
    assert fresh.json()["users"]["total"] == 2


async def test_endpoint_works_when_redis_is_down(
    app: FastAPI, client: httpx.AsyncClient, db: AsyncSession
) -> None:
    class Down:
        async def get(self, name: str) -> Any:
            raise ConnectionError("redis down")

        async def set(self, name: str, value: str, ex: int | None = None) -> Any:
            raise ConnectionError("redis down")

    app.dependency_overrides[get_stats_cache] = lambda: Down()
    _, h = await admin_headers(client, db, UserRole.admin)
    r = await client.get(f"{API}/admin/stats", headers=h)
    assert r.status_code == 200 and r.json()["users"]["total"] == 1
