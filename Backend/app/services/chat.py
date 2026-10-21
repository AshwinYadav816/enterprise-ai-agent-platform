"""Conversations, messages, rolling summary, and the streaming turn.

Streaming design: the AI run happens in its own asyncio task (ChatTurn). The HTTP response body
(relay) only forwards frames from a queue. On disconnect Starlette cancels the response, and the
relay may be abandoned without its `finally` running, so the save can't live there. ChatTurn's
own `finally` always saves the assistant message exactly once (complete / error / interrupted),
using a fresh DB session because the request's session is closed before streaming starts.
"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator, Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionFactory
from app.core.errors import AppError
from app.core.pagination import next_cursor_for, paginate
from app.models import Conversation, Document, Message, MessageRole, MessageStatus, User
from app.schemas.chat import SendMessageRequest
from app.services import audit
from app.services.ai_gateway import AgentRequest, AIGateway, ChatMessage, user_ctx
from app.services.documents import visible_to

log = logging.getLogger(__name__)

TITLE_LENGTH = 60
HISTORY_MESSAGES = 6  # sent verbatim with every turn
SUMMARY_TRIGGER = 12  # summarize when more unsummarized messages than this
SAFE_AI_ERROR = "The assistant couldn't answer right now. Please try again."

_running: set[asyncio.Task[None]] = set()  # strong refs: unfinished turns must not be GC'd


def sse_frame(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


PING_FRAME = ": ping\n\n"


# --- conversations ------------------------------------------------


def _not_found() -> AppError:
    return AppError("not_found", "Conversation not found", 404)


async def get_owned(db: AsyncSession, user: User, conversation_id: uuid.UUID) -> Conversation:
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
            Conversation.org_id == user.org_id,
        )
    )
    if conv is None:  # someone else's conversation looks exactly like a missing one
        raise _not_found()
    return conv


async def create_conversation(db: AsyncSession, user: User, title: str | None) -> Conversation:
    conv = Conversation(org_id=user.org_id, user_id=user.id, title=(title or "").strip() or None)
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return conv


async def list_conversations(
    db: AsyncSession, user: User, cursor: str | None, limit: int
) -> tuple[list[Conversation], str | None]:
    stmt = select(Conversation).where(
        Conversation.user_id == user.id, Conversation.org_id == user.org_id
    )
    page = paginate(stmt, Conversation.updated_at, Conversation.id, cursor, limit)
    rows = list((await db.scalars(page)).all())
    return rows, next_cursor_for(rows, limit, sort_attr="updated_at")


async def rename(
    db: AsyncSession, user: User, conversation_id: uuid.UUID, title: str
) -> Conversation:
    conv = await get_owned(db, user, conversation_id)
    conv.title = title.strip()
    await db.flush()
    await db.refresh(conv)
    return conv


async def delete_conversation(
    db: AsyncSession, user: User, conversation_id: uuid.UUID, ip: str | None
) -> None:
    conv = await get_owned(db, user, conversation_id)
    await audit.log(
        db,
        org_id=user.org_id,
        user_id=user.id,
        action=audit.CONVERSATION_DELETED,
        target_type="conversation",
        target_id=conv.id,
        ip=ip,
    )
    await db.delete(conv)  # messages go with it (ON DELETE CASCADE)
    await db.flush()


async def list_messages(
    db: AsyncSession, user: User, conversation_id: uuid.UUID, cursor: str | None, limit: int
) -> tuple[list[Message], str | None]:
    await get_owned(db, user, conversation_id)
    stmt = select(Message).where(Message.conversation_id == conversation_id)
    page = paginate(stmt, Message.created_at, Message.id, cursor, limit, ascending=True)
    rows = list((await db.scalars(page)).all())
    return rows, next_cursor_for(rows, limit)


# --- preparing a turn (request session, before streaming) ---------------------


async def _check_documents(db: AsyncSession, user: User, doc_ids: Sequence[uuid.UUID]) -> None:
    if not doc_ids:
        return
    found = set(
        await db.scalars(select(Document.id).where(Document.id.in_(doc_ids), visible_to(user)))
    )
    if found != set(doc_ids):
        raise AppError("document_not_found", "One or more documents were not found", 404)


async def _context_messages(db: AsyncSession, conversation_id: uuid.UUID) -> list[Message]:
    """Messages that make up the conversation context, oldest first (failed replies excluded)."""
    rows = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.status != MessageStatus.error)
        .order_by(Message.created_at, Message.id)
    )
    return list(rows)


async def _update_summary(
    db: AsyncSession, ai: AIGateway, conv: Conversation, context: list[Message]
) -> None:
    """Rolling summary: fold older messages into conv.summary, keep the last 6 verbatim."""
    if len(context) - conv.summarized_count <= SUMMARY_TRIGGER:
        return
    cut = len(context) - HISTORY_MESSAGES
    batch = [
        ChatMessage(role=m.role.value, content=m.content)
        for m in context[conv.summarized_count : cut]
    ]
    if conv.summary:
        batch.insert(0, ChatMessage(role="system", content=f"Summary so far: {conv.summary}"))
    try:
        conv.summary = await ai.summarize_history(batch)
        conv.summarized_count = cut
    except Exception:
        log.exception("Summarizing conversation %s failed; keeping the old summary", conv.id)


async def prepare_turn(
    db: AsyncSession,
    ai: AIGateway,
    user: User,
    conversation_id: uuid.UUID,
    data: SendMessageRequest,
) -> tuple[Conversation, AgentRequest]:
    conv = await get_owned(db, user, conversation_id)
    doc_ids = list(dict.fromkeys(data.doc_ids or []))
    await _check_documents(db, user, doc_ids)

    context = await _context_messages(db, conv.id)
    await _update_summary(db, ai, conv, context)
    history = [
        ChatMessage(role=m.role.value, content=m.content) for m in context[-HISTORY_MESSAGES:]
    ]

    content = data.content.strip()
    # Check "first message?" BEFORE adding it (autoflush would count the new one).
    is_first = not await db.scalar(
        select(func.count()).select_from(Message).where(Message.conversation_id == conv.id)
    )
    if is_first and not conv.title:
        conv.title = " ".join(content.split())[:TITLE_LENGTH]
    db.add(Message(conversation_id=conv.id, role=MessageRole.user, content=content))
    await db.flush()

    request = AgentRequest(
        query=content,
        user=user_ctx(user),
        history=history,
        history_summary=conv.summary,
        force_agent=data.force_agent,
        doc_ids=[str(d) for d in doc_ids] or None,
    )
    return conv, request


# --- the streaming turn ------------------------------------------------

_END = object()


class ChatTurn:
    """Runs ai.run in its own task, queues SSE frames, saves the assistant message once."""

    def __init__(
        self,
        ai: AIGateway,
        request: AgentRequest,
        conversation_id: uuid.UUID,
        session_factory: SessionFactory,
    ) -> None:
        self.ai = ai
        self.request = request
        self.conversation_id = conversation_id
        self.session_factory = session_factory
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        self.tokens: list[str] = []
        self.sources: list[dict[str, Any]] = []
        self.results: list[dict[str, Any]] = []
        self.done: dict[str, Any] | None = None
        self.message_id: uuid.UUID | None = None
        self.task: asyncio.Task[None] | None = None

    def start(self) -> "ChatTurn":
        self.task = asyncio.create_task(self._run(), name=f"chat-turn-{self.conversation_id}")
        _running.add(self.task)
        self.task.add_done_callback(_running.discard)
        return self

    def cancel(self) -> None:
        if self.task is not None and not self.task.done():
            self.task.cancel()

    async def _run(self) -> None:
        status = MessageStatus.complete
        try:
            async for event in self.ai.run(self.request):
                self._collect(event.type, event.data)
                if event.type != "done":  # our own done (with message_id) is sent after saving
                    self.queue.put_nowait(sse_frame(event.type, event.data))
        except asyncio.CancelledError:
            status = MessageStatus.interrupted
            raise
        except Exception:
            log.exception("AI run failed for conversation %s", self.conversation_id)
            status = MessageStatus.error
            self.queue.put_nowait(sse_frame("error", {"message": SAFE_AI_ERROR}))
        finally:
            await self._save(status)
            done = dict(self.done or {"answer": self._answer(), "agents": [], "errors": 1})
            done["message_id"] = str(self.message_id) if self.message_id else None
            self.queue.put_nowait(sse_frame("done", done))
            self.queue.put_nowait(_END)

    def _collect(self, kind: str, data: dict[str, Any]) -> None:
        if kind == "token":
            self.tokens.append(str(data.get("text", "")))
        elif kind == "sources":
            self.sources.extend(data.get("sources", []))
        elif kind == "result":
            self.results.append(data)
        elif kind == "done":
            self.done = data

    def _answer(self) -> str:
        if self.done and self.done.get("answer"):
            return str(self.done["answer"])
        return "".join(self.tokens).strip()

    async def _save(self, status: MessageStatus) -> None:
        usage = (self.done or {}).get("usage") or {}
        agents = (self.done or {}).get("agents") or [r.get("agent") for r in self.results]
        message = Message(
            conversation_id=self.conversation_id,
            role=MessageRole.assistant,
            content=self._answer(),
            agent=",".join(a for a in agents if a) or None,
            sources=self.sources or None,
            results=self.results or None,
            status=status,
            prompt_tokens=int(usage.get("input_tokens", 0)),
            completion_tokens=int(usage.get("output_tokens", 0)),
        )
        try:
            async with self.session_factory() as db:
                db.add(message)
                conv = await db.get(Conversation, self.conversation_id)
                if conv is not None:
                    conv.updated_at = func.clock_timestamp()  # most recent first in the list
                await db.commit()
                self.message_id = message.id
        except Exception:
            log.exception("Could not save assistant message for %s", self.conversation_id)


async def relay(turn: ChatTurn) -> AsyncIterator[str]:
    """The response body: forward queued frames, ping while waiting, stop the turn if abandoned."""
    heartbeat = get_settings().sse_heartbeat_seconds
    try:
        while True:
            try:
                item = await asyncio.wait_for(turn.queue.get(), timeout=heartbeat)
            except TimeoutError:
                yield PING_FRAME
                continue
            if item is _END:
                return
            yield item
    finally:
        turn.cancel()  # no await: safe even inside a cancelled scope; the turn saves itself
