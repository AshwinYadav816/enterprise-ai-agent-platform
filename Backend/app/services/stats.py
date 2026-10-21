"""Admin dashboard numbers: 6 aggregate queries per org, cached in Redis for 60 s."""

import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Protocol

from fastapi import Depends
from sqlalchemy import Float, Text, case, cast, func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import get_redis
from app.models import (
    Conversation,
    Document,
    DocumentStatus,
    Generation,
    GenerationKind,
    Message,
    User,
    UserRole,
)
from app.schemas.admin import (
    AdminStats,
    AgentUsage,
    CountStats,
    DocumentStats,
    GenerationStats,
    TokensPerDay,
    TokenStats,
    UserStats,
)

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60
TOKEN_DAYS = 30
ACTIVE_DAYS = 7


async def compute(db: AsyncSession, org_id: uuid.UUID, now: datetime | None = None) -> AdminStats:
    now = now or datetime.now(UTC)
    today = now.astimezone(UTC).date()
    first_day = today - timedelta(days=TOKEN_DAYS - 1)
    window_start = datetime.combine(first_day, datetime.min.time(), tzinfo=UTC)

    # 1. users by role (+ active / deactivated) ------------------------------
    active_since = now - timedelta(days=ACTIVE_DAYS)
    rows = (
        await db.execute(
            select(
                User.role,
                func.count(),
                func.count().filter(User.last_login_at >= active_since, User.is_active),
                func.count().filter(User.is_active.is_(False)),
            )
            .where(User.org_id == org_id)
            .group_by(User.role)
        )
    ).all()
    by_role = {r.value: 0 for r in UserRole} | {role.value: n for role, n, _, _ in rows}
    users = UserStats(
        total=sum(by_role.values()),
        by_role=by_role,
        active_last_7_days=sum(r[2] for r in rows),
        deactivated=sum(r[3] for r in rows),
    )

    # 2. documents by status + storage ------------------------------
    rows = (
        await db.execute(
            select(Document.status, func.count(), func.coalesce(func.sum(Document.size_bytes), 0))
            .where(Document.org_id == org_id)
            .group_by(Document.status)
        )
    ).all()
    by_status = {s.value: 0 for s in DocumentStatus} | {s.value: n for s, n, _ in rows}
    documents = DocumentStats(
        total=sum(by_status.values()),
        by_status=by_status,
        storage_bytes=int(sum(r[2] for r in rows)),
    )

    # 3. conversations + messages ------------------------------
    org_conversations = select(Conversation.id).where(Conversation.org_id == org_id)
    conv_total, msg_total = (
        await db.execute(
            select(
                select(func.count()).select_from(org_conversations.subquery()).scalar_subquery(),
                select(func.count())
                .select_from(Message)
                .where(Message.conversation_id.in_(org_conversations))
                .scalar_subquery(),
            )
        )
    ).one()

    # 4. generations by kind ------------------------------
    rows = (
        await db.execute(
            select(Generation.kind, func.count())
            .where(Generation.org_id == org_id)
            .group_by(Generation.kind)
        )
    ).all()
    by_kind = {k.value: 0 for k in GenerationKind} | {k.value: n for k, n in rows}
    generations = GenerationStats(total=sum(by_kind.values()), by_kind=by_kind)

    # 5. tokens per day (UTC) from messages + generations ------------------------------
    msg_usage = (
        select(
            Message.created_at.label("at"),
            Message.prompt_tokens.label("p"),
            Message.completion_tokens.label("c"),
        )
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.org_id == org_id, Message.created_at >= window_start)
    )
    gen_usage = select(
        Generation.created_at.label("at"),
        Generation.prompt_tokens.label("p"),
        Generation.completion_tokens.label("c"),
    ).where(Generation.org_id == org_id, Generation.created_at >= window_start)
    usage = union_all(msg_usage, gen_usage).subquery()
    day = func.date_trunc("day", func.timezone("UTC", usage.c.at)).label("day")
    rows = (
        await db.execute(
            select(day, func.sum(usage.c.p), func.sum(usage.c.c)).group_by(day).order_by(day)
        )
    ).all()
    found: dict[date, tuple[int, int]] = {d.date(): (int(p), int(c)) for d, p, c in rows}
    per_day = [
        TokensPerDay(
            date=d,
            prompt_tokens=found.get(d, (0, 0))[0],
            completion_tokens=found.get(d, (0, 0))[1],
            total_tokens=sum(found.get(d, (0, 0))),
        )
        for d in (first_day + timedelta(days=i) for i in range(TOKEN_DAYS))
    ]

    # 6. requests + tokens per agent (last 30 days) ------------------------------
    # A multi-agent reply ("meeting,email") counts as a request for each agent and its tokens are
    # split equally between them, so per-agent tokens still add up to the real total.
    agents = func.string_to_array(Message.agent, ",")
    msg_agents = (
        select(
            func.unnest(agents).label("agent"),
            (
                cast(Message.prompt_tokens + Message.completion_tokens, Float)
                / func.cardinality(agents)
            ).label("tokens"),
        )
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.org_id == org_id,
            Message.agent.is_not(None),
            Message.created_at >= window_start,
        )
    )
    gen_agents = select(
        case(
            (Generation.kind == GenerationKind.document_insights, "document"),
            else_=cast(Generation.kind, Text),
        ).label("agent"),
        cast(Generation.prompt_tokens + Generation.completion_tokens, Float).label("tokens"),
    ).where(Generation.org_id == org_id, Generation.created_at >= window_start)
    by_agent = union_all(msg_agents, gen_agents).subquery()
    rows = (
        await db.execute(
            select(by_agent.c.agent, func.count(), func.sum(by_agent.c.tokens)).group_by(
                by_agent.c.agent
            )
        )
    ).all()
    per_agent = sorted(
        (AgentUsage(agent=str(a), requests=int(n), tokens=round(t or 0)) for a, n, t in rows),
        key=lambda u: (-u.tokens, u.agent),
    )

    return AdminStats(
        generated_at=now,
        users=users,
        documents=documents,
        conversations=CountStats(total=int(conv_total)),
        messages=CountStats(total=int(msg_total)),
        generations=generations,
        tokens=TokenStats(
            last_30_days_total=sum(d.total_tokens for d in per_day),
            per_day=per_day,
            per_agent=per_agent,
        ),
    )


# --- cache ------------------------------------------


class KeyValue(Protocol):
    async def get(self, name: str) -> Any: ...
    async def set(self, name: str, value: str, ex: int | None = None) -> Any: ...


def get_stats_cache() -> KeyValue:
    return get_redis()


StatsCache = Annotated[KeyValue, Depends(get_stats_cache)]


def _cache_key(org_id: uuid.UUID) -> str:
    return f"stats:{org_id}"


async def get_stats(db: AsyncSession, cache: KeyValue, org_id: uuid.UUID) -> AdminStats:
    """Cached for 60 s per org; any Redis problem just means computing fresh."""
    try:
        if cached := await cache.get(_cache_key(org_id)):
            return AdminStats.model_validate_json(cached)
    except Exception as exc:
        log.warning("Stats cache read failed (%s); computing", exc)
    stats = await compute(db, org_id)
    try:
        await cache.set(_cache_key(org_id), stats.model_dump_json(), ex=CACHE_TTL_SECONDS)
    except Exception as exc:
        log.warning("Stats cache write failed (%s)", exc)
    return stats
