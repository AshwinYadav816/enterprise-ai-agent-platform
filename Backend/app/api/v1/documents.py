import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, Response, UploadFile, status
from fastapi.responses import RedirectResponse

from app.core.db import DbSession, SessionFactoryDep
from app.core.deps import ClientIP, CurrentUser
from app.core.pagination import DEFAULT_LIMIT, CursorParam, LimitParam, Page
from app.models import DocumentStatus, UserRole
from app.schemas.documents import DocumentOut
from app.services import documents as documents_service
from app.services.ai_gateway import AI
from app.services.storage import StorageDep

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    user: CurrentUser,
    db: DbSession,
    storage: StorageDep,
    ai: AI,
    session_factory: SessionFactoryDep,
    background: BackgroundTasks,
    ip: ClientIP,
    file: Annotated[UploadFile, File(description="pdf, docx, pptx or xlsx")],
    visibility: Annotated[UserRole, Form(description="Lowest role allowed to see it")] = (
        UserRole.employee
    ),
) -> DocumentOut:
    """Accepts the file and returns at once with status `processing`; poll GET /documents/{id}."""
    doc = await documents_service.upload(db, storage, user, file, visibility, ip)
    background.add_task(documents_service.process_document, doc.id, session_factory, ai, storage)
    return DocumentOut.model_validate(doc)


@router.get("")
async def list_documents(
    user: CurrentUser,
    db: DbSession,
    status: DocumentStatus | None = None,
    search: Annotated[str | None, Query(max_length=200, description="filename contains")] = None,
    cursor: CursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> Page[DocumentOut]:
    rows, next_cursor = await documents_service.list_documents(
        db, user, status=status, search=search, cursor=cursor, limit=limit
    )
    return Page(items=[DocumentOut.model_validate(d) for d in rows], next_cursor=next_cursor)


@router.get("/{document_id}")
async def get_document(document_id: uuid.UUID, user: CurrentUser, db: DbSession) -> DocumentOut:
    return DocumentOut.model_validate(await documents_service.get_visible(db, user, document_id))


@router.get(
    "/{document_id}/download",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}, 307: {}},
)
async def download_document(
    document_id: uuid.UUID, user: CurrentUser, db: DbSession, storage: StorageDep
) -> Response:
    doc = await documents_service.get_visible(db, user, document_id)
    if url := await storage.url_or_none(doc.storage_key, doc.filename):
        return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    data = await storage.open(doc.storage_key)
    disposition = f"attachment; filename*=UTF-8''{quote(doc.filename)}"
    return Response(
        data,
        media_type=doc.content_type,
        headers={"Content-Disposition": disposition, "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    ai: AI,
    storage: StorageDep,
    ip: ClientIP,
) -> None:
    """Owner or admin: removes the vectors, the file and the record."""
    await documents_service.delete(db, ai, storage, user, document_id, ip)
