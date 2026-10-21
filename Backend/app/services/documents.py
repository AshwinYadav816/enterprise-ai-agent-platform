"""Document upload, background ingestion, visibility-filtered access, deletion."""

import logging
import uuid
from collections.abc import Sequence
from pathlib import PurePosixPath

from fastapi import UploadFile
from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionFactory
from app.core.errors import AppError
from app.core.pagination import next_cursor_for, paginate
from app.core.security import expand_roles
from app.models import Document, DocumentStatus, User, UserRole
from app.services import audit
from app.services.ai_gateway import AIGateway, AIIngestError, DocMeta
from app.services.storage import Storage, document_key, safe_filename

log = logging.getLogger(__name__)

READ_CHUNK = 1024 * 1024
CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
# First bytes of each format: catches renamed files before they reach the parser.
_SIGNATURES = {"pdf": b"%PDF", "docx": b"PK\x03\x04", "pptx": b"PK\x03\x04", "xlsx": b"PK\x03\x04"}
GENERIC_INGEST_ERROR = "Processing failed. Please try uploading the file again."


def _not_found() -> AppError:
    return AppError("not_found", "Document not found", 404)


def visible_to(user: User) -> ColumnElement[bool]:
    """Org + role visibility: the same rule the AI module applies in Qdrant."""
    return (Document.org_id == user.org_id) & Document.allowed_roles.overlap(
        expand_roles(user.role)
    )


async def read_upload(file: UploadFile, max_bytes: int) -> bytes:
    """Read in chunks and stop as soon as the limit is passed (never buffer a huge file)."""
    parts: list[bytes] = []
    total = 0
    while chunk := await file.read(READ_CHUNK):
        total += len(chunk)
        if total > max_bytes:
            raise AppError(
                "file_too_large", f"File is larger than the {max_bytes // 2**20} MB limit", 413
            )
        parts.append(chunk)
    return b"".join(parts)


def validate_file(filename: str, data: bytes) -> str:
    """Returns the lowercase extension; rejects unsupported, empty or mislabelled files."""
    allowed = [e.lower() for e in get_settings().allowed_extensions]
    ext = PurePosixPath(filename).suffix.lower().lstrip(".")
    if ext not in allowed:
        raise AppError(
            "unsupported_file_type", f"Only {', '.join(allowed)} files are supported", 400
        )
    if not data:
        raise AppError("empty_file", "The file is empty", 400)
    signature = _SIGNATURES.get(ext)
    if signature and not data.startswith(signature):
        raise AppError("invalid_file", f"This doesn't look like a valid .{ext} file", 400)
    return ext


async def upload(
    db: AsyncSession,
    storage: Storage,
    user: User,
    file: UploadFile,
    visibility: UserRole,
    ip: str | None,
) -> Document:
    """Save the file and a `processing` row, and commit. The caller schedules ingestion."""
    if visibility.value not in expand_roles(user.role):
        raise AppError(
            "visibility_not_allowed", "You can't upload a document you wouldn't be able to see", 400
        )
    data = await read_upload(file, get_settings().max_upload_mb * 2**20)
    filename = safe_filename(file.filename or "upload")
    ext = validate_file(filename, data)

    doc_id = uuid.uuid4()
    key = document_key(user.org_id, doc_id, filename)
    await storage.save(key, data)
    doc = Document(
        id=doc_id,
        org_id=user.org_id,
        owner_id=user.id,
        filename=filename,
        content_type=CONTENT_TYPES.get(ext, "application/octet-stream"),
        size_bytes=len(data),
        storage_key=key,
        allowed_roles=[visibility.value],
        status=DocumentStatus.processing,
    )
    db.add(doc)
    await audit.log(
        db,
        org_id=user.org_id,
        user_id=user.id,
        action=audit.DOCUMENT_UPLOADED,
        target_type="document",
        target_id=doc_id,
        meta={"filename": filename, "size_bytes": len(data), "visibility": visibility.value},
        ip=ip,
    )
    try:
        await db.commit()  # the background task reads this row from its own session
    except BaseException:
        await storage.delete(key)  # don't leave an orphan file behind
        raise
    await db.refresh(doc)
    return doc


async def process_document(
    doc_id: uuid.UUID, session_factory: SessionFactory, ai: AIGateway, storage: Storage
) -> None:
    """Background task: ingest into the AI module and record the outcome. Never raises."""
    async with session_factory() as db:
        doc = await db.get(Document, doc_id)
        if doc is None:
            return
        meta = DocMeta(
            doc_id=str(doc.id),
            org_id=str(doc.org_id),
            owner_id=str(doc.owner_id),
            allowed_roles=list(doc.allowed_roles),
        )
        try:
            data = await storage.open(doc.storage_key)
            result = await ai.ingest_document(data, doc.filename, meta)
        except AIIngestError as exc:  # user-safe message from the AI module
            doc.status, doc.error = DocumentStatus.failed, str(exc)[:500]
        except Exception:
            log.exception("Ingestion failed for document %s", doc_id)
            doc.status, doc.error = DocumentStatus.failed, GENERIC_INGEST_ERROR
        else:
            doc.status = DocumentStatus.ready
            doc.chunk_count, doc.page_count = result.chunks, result.pages
            doc.warnings, doc.error = list(result.warnings), None

        try:
            await db.commit()
        except Exception:
            log.exception("Could not save ingestion result for document %s", doc_id)
            return

        # Deleted while we were ingesting? Then the vectors we just wrote are orphans.
        # (A fresh query after commit sees deletes committed by other requests.)
        still_there = await db.scalar(select(Document.id).where(Document.id == doc_id))
        if still_there is None:
            try:
                await ai.delete_document(str(doc_id), meta.org_id)
            except Exception:
                log.exception("Could not remove vectors of deleted document %s", doc_id)


async def list_documents(
    db: AsyncSession,
    user: User,
    *,
    status: DocumentStatus | None,
    search: str | None,
    cursor: str | None,
    limit: int,
) -> tuple[list[Document], str | None]:
    stmt = select(Document).where(visible_to(user))
    if status:
        stmt = stmt.where(Document.status == status)
    if search and (term := search.strip()):
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(Document.filename.ilike(f"%{escaped}%", escape="\\"))
    rows = list(
        (await db.scalars(paginate(stmt, Document.created_at, Document.id, cursor, limit))).all()
    )
    return rows, next_cursor_for(rows, limit)


async def ensure_visible(
    db: AsyncSession, user: User, doc_ids: Sequence[uuid.UUID], *, require_ready: bool = False
) -> None:
    """All ids must be documents this user may see (else one generic 404, no hints).

    require_ready: also refuse documents still processing or failed (409) — the AI would
    otherwise silently answer "not found" for them.
    """
    if not doc_ids:
        return
    rows = (
        await db.execute(
            select(Document.id, Document.filename, Document.status).where(
                Document.id.in_(doc_ids), visible_to(user)
            )
        )
    ).all()
    if {r.id for r in rows} != set(doc_ids):
        raise AppError("document_not_found", "One or more documents were not found", 404)
    if require_ready and (
        pending := [r.filename for r in rows if r.status is not DocumentStatus.ready]
    ):
        raise AppError(
            "document_not_ready", f"Not ready yet (processing or failed): {', '.join(pending)}", 409
        )


async def get_visible(db: AsyncSession, user: User, doc_id: uuid.UUID) -> Document:
    doc = await db.scalar(select(Document).where(Document.id == doc_id, visible_to(user)))
    if doc is None:  # missing, other org and not-allowed all look the same
        raise _not_found()
    return doc


async def delete(
    db: AsyncSession,
    ai: AIGateway,
    storage: Storage,
    user: User,
    doc_id: uuid.UUID,
    ip: str | None,
) -> None:
    doc = await get_visible(db, user, doc_id)
    if doc.owner_id != user.id and user.role is not UserRole.admin:
        raise AppError("forbidden", "Only the owner or an admin can delete this document", 403)
    try:
        await ai.delete_document(str(doc.id), str(doc.org_id))
    except Exception as exc:
        log.exception("Vector delete failed for document %s", doc.id)
        raise AppError(
            "ai_unavailable", "Couldn't delete the document right now. Please retry.", 502
        ) from exc
    await storage.delete(doc.storage_key)
    await audit.log(
        db,
        org_id=doc.org_id,
        user_id=user.id,
        action=audit.DOCUMENT_DELETED,
        target_type="document",
        target_id=doc.id,
        meta={"filename": doc.filename},
        ip=ip,
    )
    await db.delete(doc)
    await db.flush()
