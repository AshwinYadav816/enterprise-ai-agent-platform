"""Tools: meeting summary, report, email, document insights; saved generations + PDF."""

import uuid
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from app.core.db import DbSession
from app.core.deps import ClientIP, CurrentUser
from app.core.errors import AppError
from app.core.pagination import DEFAULT_LIMIT, CursorParam, LimitParam, Page
from app.core.ratelimit import Limiter
from app.models import GenerationKind, User
from app.schemas.tools import (
    EmailRequest,
    GenerationOut,
    GenerationSummary,
    MeetingRequest,
    ReportRequest,
)
from app.services import tools as tools_service
from app.services.ai_gateway import AI

router = APIRouter(prefix="/tools", tags=["tools"])


async def _ai_allowed(user: CurrentUser, limiter: Limiter) -> User:
    await limiter.ai(user.id, user.org_id)
    return user


AIUser = Annotated[User, Depends(_ai_allowed)]


def _validation_error(exc: ValidationError) -> AppError:
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"]) or "body"
    return AppError("validation_error", f"{field}: {first['msg']}", 422)


_MEETING_BODY: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {"schema": MeetingRequest.model_json_schema()},
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["file"],
                    "properties": {
                        "file": {
                            "type": "string",
                            "format": "binary",
                            "description": ".txt, .vtt or .docx",
                        },
                        "title": {"type": "string"},
                    },
                }
            },
        },
    }
}


@router.post("/meetings", status_code=status.HTTP_201_CREATED, openapi_extra=_MEETING_BODY)
async def summarize_meeting(
    request: Request, user: AIUser, db: DbSession, ai: AI, ip: ClientIP
) -> GenerationOut:
    """Summarize a meeting. Send JSON `{transcript, title?}` or multipart `file` (+ `title`)."""
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        form = await request.form()
        file = form.get("file")
        if not isinstance(file, UploadFile):
            raise AppError("validation_error", "file: a transcript file is required", 422)
        transcript = await tools_service.transcript_from_file(file)
        title = form.get("title")
        title = title if isinstance(title, str) else None
    else:
        try:
            body = MeetingRequest.model_validate_json(await request.body())
        except ValidationError as exc:
            raise _validation_error(exc) from exc
        transcript, title = body.transcript, body.title
    gen = await tools_service.meeting(db, ai, user, transcript, title, ip)
    return GenerationOut.model_validate(gen)


@router.post("/reports", status_code=status.HTTP_201_CREATED)
async def write_report(
    data: ReportRequest, user: AIUser, db: DbSession, ai: AI, ip: ClientIP
) -> GenerationOut:
    return GenerationOut.model_validate(await tools_service.report(db, ai, user, data, ip))


@router.post("/emails", status_code=status.HTTP_201_CREATED)
async def write_email(
    data: EmailRequest, user: AIUser, db: DbSession, ai: AI, ip: ClientIP
) -> GenerationOut:
    return GenerationOut.model_validate(await tools_service.email(db, ai, user, data, ip))


@router.post("/documents/{document_id}/insights", status_code=status.HTTP_201_CREATED)
async def document_insights(
    document_id: uuid.UUID, user: AIUser, db: DbSession, ai: AI, ip: ClientIP
) -> GenerationOut:
    gen = await tools_service.document_insights(db, ai, user, document_id, ip)
    return GenerationOut.model_validate(gen)


@router.get("/generations")
async def list_generations(
    user: CurrentUser,
    db: DbSession,
    kind: Annotated[GenerationKind | None, Query()] = None,
    cursor: CursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> Page[GenerationSummary]:
    rows, next_cursor = await tools_service.list_generations(db, user, kind, cursor, limit)
    return Page(items=[GenerationSummary.model_validate(g) for g in rows], next_cursor=next_cursor)


@router.get("/generations/{generation_id}")
async def get_generation(
    generation_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> GenerationOut:
    return GenerationOut.model_validate(await tools_service.get_owned(db, user, generation_id))


@router.get(
    "/generations/{generation_id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def download_pdf(
    generation_id: uuid.UUID, user: CurrentUser, db: DbSession, ai: AI
) -> Response:
    gen = await tools_service.get_owned(db, user, generation_id)
    pdf, filename = await tools_service.pdf_for(ai, gen)
    disposition = f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": disposition})
