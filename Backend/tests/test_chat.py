import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    Conversation,
    Document,
    Message,
    MessageRole,
    MessageStatus,
    User,
    UserRole,
)
from app.services.ai_gateway import AgentRequest, ChatMessage, Event, FakeAIGateway, get_ai
from app.services.chat import SAFE_AI_ERROR, ChatTurn, relay
from tests.factories import make_org, make_user

API = "/api/v1"
PASSWORD = "correct-horse-battery"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def auth(client: httpx.AsyncClient, user: User) -> dict[str, str]:
    r = await client.post(f"{API}/auth/login", json={"email": user.email, "password": PASSWORD})
    return bearer(r.json()["access_token"])


def parse_sse(body: str) -> tuple[list[tuple[str, dict[str, Any]]], int]:
    """(frames as (event, data), number of ': ping' heartbeats)."""
    frames, pings = [], 0
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        if block.startswith(": ping"):
            pings += 1
            continue
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        frames.append((lines["event"], json.loads(lines["data"])))
    return frames, pings


async def setup_chat(
    client: httpx.AsyncClient, db: AsyncSession, role: UserRole = UserRole.employee
) -> tuple[User, dict[str, str], str]:
    user = await make_user(db, role=role, password=PASSWORD)
    h = await auth(client, user)
    conv = await client.post(f"{API}/conversations", headers=h)
    assert conv.status_code == 201
    return user, h, conv.json()["id"]


async def send(
    client: httpx.AsyncClient, h: dict[str, str], conv_id: str, **body: Any
) -> httpx.Response:
    return await client.post(
        f"{API}/conversations/{conv_id}/messages", headers=h, json={"content": "hi", **body}
    )


# --- streaming + saving ----------------------------------------------


async def test_frames_in_order_and_reply_saved(
    client: httpx.AsyncClient, db: AsyncSession, fake_ai: FakeAIGateway
) -> None:
    user, h, conv_id = await setup_chat(client, db, role=UserRole.manager)
    question = "What does our travel policy say about hotels?\nPlease keep it short and cite it."
    r = await send(client, h, conv_id, content=question)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["cache-control"] == "no-cache" and r.headers["x-accel-buffering"] == "no"

    frames, _ = parse_sse(r.text)
    kinds = [k for k, _ in frames]
    assert kinds[:4] == ["status", "status", "agent", "sources"]
    assert kinds[-2:] == ["result", "done"] and set(kinds[4:-2]) == {"token"}
    done = frames[-1][1]
    assert done["answer"] == "This is a fake answer [1]." and done["usage"]["total_tokens"] == 150
    message_id = uuid.UUID(done["message_id"])

    (req,) = fake_ai.requests
    assert req.query == question and req.history == [] and req.history_summary is None
    assert req.user.roles == ["employee", "manager"] and req.user.org_id == str(user.org_id)

    reply = await db.get(Message, message_id)
    assert reply is not None and reply.role is MessageRole.assistant
    assert reply.status is MessageStatus.complete and reply.content == done["answer"]
    assert (
        reply.agent == "research" and reply.prompt_tokens == 120 and reply.completion_tokens == 30
    )
    assert reply.results and reply.results[0]["agent"] == "research"

    conv = await db.get(Conversation, uuid.UUID(conv_id))
    assert conv is not None and conv.title == " ".join(question.split())[:60]
    assert "\n" not in conv.title and len(conv.title) == 60  # one line, first 60 chars
    history = (await client.get(f"{API}/conversations/{conv_id}/messages", headers=h)).json()
    assert [m["role"] for m in history["items"]] == ["user", "assistant"]  # oldest → newest
    assert history["items"][0]["content"] == question


async def test_force_agent_and_doc_ids_reach_the_ai(
    client: httpx.AsyncClient, db: AsyncSession, fake_ai: FakeAIGateway
) -> None:
    user, h, conv_id = await setup_chat(client, db)
    doc = Document(
        org_id=user.org_id,
        owner_id=user.id,
        filename="t.pdf",
        content_type="application/pdf",
        size_bytes=1,
        storage_key="k/t.pdf",
        allowed_roles=["employee"],
    )
    db.add(doc)
    await db.flush()
    r = await send(client, h, conv_id, force_agent="meeting", doc_ids=[str(doc.id), str(doc.id)])
    frames, _ = parse_sse(r.text)
    assert frames[-2][1]["agent"] == "meeting" and "markdown" in frames[-2][1]
    (req,) = fake_ai.requests
    assert req.force_agent is not None and req.force_agent.value == "meeting"
    assert req.doc_ids == [str(doc.id)]  # de-duplicated


# --- rolling summary ----------------------------------------------


class SummaryRecorder(FakeAIGateway):
    def __init__(self) -> None:
        super().__init__()
        self.summaries: list[list[ChatMessage]] = []

    async def summarize_history(self, messages: Sequence[ChatMessage]) -> str:
        self.summaries.append(list(messages))
        return f"summary #{len(self.summaries)}"


async def test_summary_after_13_messages_and_not_rerun(
    app: FastAPI, client: httpx.AsyncClient, db: AsyncSession
) -> None:
    ai = SummaryRecorder()
    app.dependency_overrides[get_ai] = lambda: ai
    _, h, conv_id = await setup_chat(client, db)
    for i in range(13):
        role = MessageRole.user if i % 2 == 0 else MessageRole.assistant
        db.add(Message(conversation_id=uuid.UUID(conv_id), role=role, content=f"m{i}"))
    await db.flush()

    await send(client, h, conv_id, content="question 14")
    (batch,) = ai.summaries
    assert [m.content for m in batch] == [f"m{i}" for i in range(7)]  # all but the last 6
    req = ai.requests[-1]
    assert req.history_summary == "summary #1"
    assert [m.content for m in req.history] == [f"m{i}" for i in range(7, 13)]
    conv = await db.get(Conversation, uuid.UUID(conv_id))
    assert conv is not None and conv.summarized_count == 7

    await send(client, h, conv_id, content="question 16")  # next turn: no new summary
    assert len(ai.summaries) == 1 and ai.requests[-1].history_summary == "summary #1"
    assert [m.content for m in ai.requests[-1].history][-1] == "This is a fake answer [1]."

    for i in range(4):  # 4 turns later it folds the next batch, starting from the old summary
        await send(client, h, conv_id, content=f"more {i}")
    assert len(ai.summaries) == 2
    assert ai.summaries[1][0].role == "system" and "summary #1" in ai.summaries[1][0].content


# --- access + validation ----------------------------------------------


async def test_other_users_conversation_is_404(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, _, conv_id = await setup_chat(client, db)
    intruder = await make_user(db, password=PASSWORD)  # other org
    colleague = await make_user(db, await make_org(db), password=PASSWORD)
    for other in (intruder, colleague):
        h = await auth(client, other)
        for method, path, body in (
            ("POST", "/messages", {"content": "hi"}),
            ("GET", "/messages", None),
            ("PATCH", "", {"title": "x"}),
            ("DELETE", "", None),
        ):
            r = await client.request(
                method, f"{API}/conversations/{conv_id}{path}", headers=h, json=body
            )
            assert r.status_code == 404, (method, path)


async def test_invisible_doc_id_is_404(client: httpx.AsyncClient, db: AsyncSession) -> None:
    user, h, conv_id = await setup_chat(client, db)
    secret = Document(
        org_id=user.org_id,
        owner_id=user.id,
        filename="salaries.xlsx",
        content_type="x",
        size_bytes=1,
        storage_key="k/s.xlsx",
        allowed_roles=["manager"],
    )
    db.add(secret)
    await db.flush()
    for doc_id in (secret.id, uuid.uuid4()):
        r = await send(client, h, conv_id, doc_ids=[str(doc_id)])
        assert r.status_code == 404 and r.json()["error"]["code"] == "document_not_found"
    count = await db.scalar(select(Message.id).where(Message.conversation_id == uuid.UUID(conv_id)))
    assert count is None  # nothing saved for rejected requests


async def test_ai_rate_limit(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_PER_MIN", "1")
    get_settings.cache_clear()
    _, h, conv_id = await setup_chat(client, db)
    assert (await send(client, h, conv_id)).status_code == 200
    blocked = await send(client, h, conv_id)
    assert blocked.status_code == 429 and blocked.json()["error"]["code"] == "rate_limited"


# --- failures, disconnects, heartbeat ----------------------------------------------


class Crashing(FakeAIGateway):
    async def run(self, req: AgentRequest) -> AsyncIterator[Event]:
        yield Event(type="token", data={"text": "Partial "})
        raise RuntimeError("qdrant at 10.0.0.5 refused connection")


async def test_ai_error_frame_and_saved_error(
    app: FastAPI, client: httpx.AsyncClient, db: AsyncSession
) -> None:
    app.dependency_overrides[get_ai] = lambda: Crashing()
    _, h, conv_id = await setup_chat(client, db)
    r = await send(client, h, conv_id)
    frames, _ = parse_sse(r.text)
    assert [k for k, _ in frames] == ["token", "error", "done"]
    assert frames[1][1] == {"message": SAFE_AI_ERROR} and "10.0.0.5" not in r.text
    reply = await db.get(Message, uuid.UUID(frames[-1][1]["message_id"]))
    assert reply is not None and reply.status is MessageStatus.error
    assert reply.content == "Partial"
    # failed replies are left out of the next turn's history
    history = (await client.get(f"{API}/conversations/{conv_id}/messages", headers=h)).json()
    assert len(history["items"]) == 2


class Slow(FakeAIGateway):
    def __init__(self, delay: float) -> None:
        super().__init__()
        self.delay = delay

    async def run(self, req: AgentRequest) -> AsyncIterator[Event]:
        for word in ("one", "two", "three", "four"):
            await asyncio.sleep(self.delay)
            yield Event(type="token", data={"text": word + " "})
        yield Event(type="done", data={"answer": "one two three four", "agents": ["chat"]})


async def test_disconnect_saves_interrupted(db: AsyncSession) -> None:
    user = await make_user(db)
    conv = Conversation(org_id=user.org_id, user_id=user.id)
    db.add(conv)
    await db.flush()

    @asynccontextmanager
    async def session_factory() -> AsyncIterator[AsyncSession]:
        yield db

    from app.services.ai_gateway import UserCtx

    request = AgentRequest(query="hi", user=UserCtx(user_id="u", org_id="o", roles=["employee"]))
    turn = ChatTurn(Slow(delay=0.05), request, conv.id, session_factory).start()
    stream = relay(turn)
    received = [await anext(stream), await anext(stream)]  # two tokens, then the client leaves
    await stream.aclose()
    assert turn.task is not None
    with pytest.raises(asyncio.CancelledError):
        await turn.task

    reply = await db.scalar(select(Message).where(Message.conversation_id == conv.id))
    assert reply is not None and reply.status is MessageStatus.interrupted
    assert reply.content == "one two" and len(received) == 2  # what the user had seen


async def test_heartbeat_while_waiting(
    app: FastAPI, client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SSE_HEARTBEAT_SECONDS", "0.01")
    get_settings.cache_clear()
    app.dependency_overrides[get_ai] = lambda: Slow(delay=0.05)
    _, h, conv_id = await setup_chat(client, db)
    frames, pings = parse_sse((await send(client, h, conv_id)).text)
    assert pings >= 3 and frames[-1][0] == "done"


# --- conversation CRUD ----------------------------------------------


async def test_conversation_crud_and_ordering(client: httpx.AsyncClient, db: AsyncSession) -> None:
    user = await make_user(db, password=PASSWORD)
    h = await auth(client, user)
    first = (await client.post(f"{API}/conversations", headers=h, json={"title": "Q1"})).json()
    second = (await client.post(f"{API}/conversations", headers=h)).json()
    assert second["title"] is None

    order = lambda: client.get(f"{API}/conversations", headers=h)  # noqa: E731
    assert [c["id"] for c in (await order()).json()["items"]] == [second["id"], first["id"]]
    await send(client, h, first["id"])  # activity moves it to the top
    assert [c["id"] for c in (await order()).json()["items"]] == [first["id"], second["id"]]

    renamed = await client.patch(
        f"{API}/conversations/{second['id']}", headers=h, json={"title": " Budget "}
    )
    assert renamed.json()["title"] == "Budget"
    assert (await client.delete(f"{API}/conversations/{first['id']}", headers=h)).status_code == 204
    gone = await client.get(f"{API}/conversations/{first['id']}/messages", headers=h)
    assert gone.status_code == 404
    left = await db.scalar(
        select(Message.id).where(Message.conversation_id == uuid.UUID(first["id"]))
    )
    assert left is None  # messages deleted with it


async def test_message_pagination_oldest_first(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, h, conv_id = await setup_chat(client, db)
    for i in range(5):
        db.add(Message(conversation_id=uuid.UUID(conv_id), role=MessageRole.user, content=f"m{i}"))
    await db.flush()
    url = f"{API}/conversations/{conv_id}/messages"
    page1 = (await client.get(url, headers=h, params={"limit": "3"})).json()
    page2 = (
        await client.get(url, headers=h, params={"limit": "3", "cursor": page1["next_cursor"]})
    ).json()
    assert [m["content"] for m in page1["items"] + page2["items"]] == [f"m{i}" for i in range(5)]
    assert page2["next_cursor"] is None
