import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Path, Response, status
from fastapi.responses import StreamingResponse

from app.core.db import DbSession, SessionFactoryDep
from app.core.deps import ClientIP, CurrentUser
from app.core.pagination import DEFAULT_LIMIT, CursorParam, LimitParam, Page
from app.core.ratelimit import Limiter
from app.schemas.chat import (
    ConversationOut,
    CreateConversationRequest,
    MessageOut,
    SendMessageRequest,
    UpdateConversationRequest,
)
from app.services import chat as chat_service
from app.services.ai_gateway import AI

router = APIRouter(prefix="/conversations", tags=["conversations"])

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.get("")
async def list_conversations(
    user: CurrentUser, db: DbSession, cursor: CursorParam = None, limit: LimitParam = DEFAULT_LIMIT
) -> Page[ConversationOut]:
    """Your conversations, most recently active first."""
    rows, next_cursor = await chat_service.list_conversations(db, user, cursor, limit)
    return Page(items=[ConversationOut.model_validate(c) for c in rows], next_cursor=next_cursor)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    user: CurrentUser, db: DbSession, data: CreateConversationRequest | None = None
) -> ConversationOut:
    conv = await chat_service.create_conversation(db, user, data.title if data else None)
    return ConversationOut.model_validate(conv)


@router.patch("/{conversation_id}")
async def rename_conversation(
    conversation_id: uuid.UUID, data: UpdateConversationRequest, user: CurrentUser, db: DbSession
) -> ConversationOut:
    return ConversationOut.model_validate(
        await chat_service.rename(db, user, conversation_id, data.title)
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, db: DbSession, ip: ClientIP
) -> None:
    await chat_service.delete_conversation(db, user, conversation_id, ip)


@router.get("/{conversation_id}/messages")
async def list_messages(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    cursor: CursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> Page[MessageOut]:
    """History oldest → newest."""
    rows, next_cursor = await chat_service.list_messages(db, user, conversation_id, cursor, limit)
    return Page(items=[MessageOut.model_validate(m) for m in rows], next_cursor=next_cursor)


@router.post(
    "/{conversation_id}/messages",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "SSE stream"}},
)
async def send_message(
    conversation_id: uuid.UUID,
    data: SendMessageRequest,
    user: CurrentUser,
    db: DbSession,
    ai: AI,
    limiter: Limiter,
    session_factory: SessionFactoryDep,
) -> StreamingResponse:
    """Ask the assistant. Streams `event:`/`data:` frames: status, agent, sources, token, result,
    error, done (`done.message_id` is the saved reply). `: ping` comments keep the line alive."""
    await limiter.ai(user.id, user.org_id)
    conv, request = await chat_service.prepare_turn(db, ai, user, conversation_id, data)
    # The user message is committed before streaming starts (DbSession scope="function").
    turn = chat_service.ChatTurn(ai, request, conv.id, session_factory).start()
    return StreamingResponse(
        chat_service.relay(turn), media_type="text/event-stream", headers=SSE_HEADERS
    )


@router.get(
    "/{conversation_id}/messages/{message_id}/results/{index}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def result_pdf(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    index: Annotated[int, Path(ge=0, le=10)],
    user: CurrentUser,
    db: DbSession,
    ai: AI,
) -> Response:
    """Download one result of an assistant reply (`message.results[index]`) as a PDF."""
    pdf, filename = await chat_service.result_pdf(db, ai, user, conversation_id, message_id, index)
    disposition = f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": disposition})
