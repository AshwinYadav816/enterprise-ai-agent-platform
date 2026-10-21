"""Tools (meeting summary, report, email, document insights): one AI call → one saved generation."""

import asyncio
import io
import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.pagination import next_cursor_for, paginate
from app.models import DocumentStatus, Generation, GenerationKind, User
from app.schemas.tools import MAX_TRANSCRIPT_CHARS, EmailRequest, ReportRequest
from app.services import audit
from app.services.ai_gateway import AgentName, AgentRequest, AIGateway, user_ctx
from app.services.documents import ensure_visible, get_visible, read_upload
from app.services.markdown import render

log = logging.getLogger(__name__)

AI_FAILED = "AI could not complete this request"
TRANSCRIPT_EXTENSIONS = ("txt", "vtt", "docx")
MAX_TRANSCRIPT_FILE_BYTES = 5 * 2**20
MEETING_QUERY = (
    "Summarize this meeting: key decisions, action items with owners and due dates, open questions."
)

_KIND_AGENT = {
    GenerationKind.meeting: AgentName.meeting,
    GenerationKind.report: AgentName.report,
    GenerationKind.email: AgentName.email,
    GenerationKind.document_insights: AgentName.document,
}


async def run_tool(
    db: AsyncSession,
    ai: AIGateway,
    user: User,
    kind: GenerationKind,
    query: str,
    *,
    title: str,
    input_data: dict[str, Any],
    transcript: str | None = None,
    doc_ids: list[uuid.UUID] | None = None,
    ip: str | None = None,
) -> Generation:
    """Run one agent (router skipped), keep its last result, save it as a generation."""
    agent = _KIND_AGENT[kind]
    request = AgentRequest(
        query=query,
        user=user_ctx(user),
        force_agent=agent,
        transcript=transcript,
        doc_ids=[str(d) for d in doc_ids] if doc_ids else None,
    )
    result: dict[str, Any] | None = None
    errors: list[str] = []
    usage: dict[str, Any] = {}
    try:
        async for event in ai.run(request):
            if event.type == "result" and event.data.get("agent") == agent.value:
                result = event.data
            elif event.type == "error":
                errors.append(str(event.data.get("message") or ""))
            elif event.type == "done":
                usage = event.data.get("usage") or {}
    except Exception as exc:
        log.exception("Tool %s failed", kind.value)
        raise AppError("ai_failed", AI_FAILED, 502) from exc
    if result is None or errors:
        # The AI's step errors are user-safe (e.g. "Please provide a meeting transcript").
        detail = next((e for e in errors if e), None)
        raise AppError("ai_failed", f"{AI_FAILED}: {detail}" if detail else AI_FAILED, 502)

    output = dict(result.get("output") or {})
    title = _title_for(kind, output, title)
    markdown = result.get("markdown") or render(kind, output, title)
    gen = Generation(
        org_id=user.org_id,
        user_id=user.id,
        kind=kind,
        title=title,
        input=input_data,
        output=output,
        markdown=markdown,
        prompt_tokens=int(usage.get("input_tokens", 0)),
        completion_tokens=int(usage.get("output_tokens", 0)),
    )
    db.add(gen)
    await db.flush()
    await audit.log(
        db,
        org_id=user.org_id,
        user_id=user.id,
        action=audit.GENERATION_CREATED,
        target_type="generation",
        target_id=gen.id,
        meta={"kind": kind.value},
        ip=ip,
    )
    await db.refresh(gen)
    return gen


def _title_for(kind: GenerationKind, output: dict[str, Any], given: str) -> str:
    """Prefer what the AI produced (report title, email subject) over the generic default."""
    if kind is GenerationKind.report and output.get("title"):
        return str(output["title"])[:200]
    if kind is GenerationKind.email and output.get("subject"):
        return str(output["subject"])[:200]
    return given[:200]


# --- the four tools ---------------------------------------------------------------------


def _today() -> str:
    return datetime.now(UTC).strftime("%d %b %Y")


async def meeting(
    db: AsyncSession, ai: AIGateway, user: User, transcript: str, title: str | None, ip: str | None
) -> Generation:
    transcript = transcript.strip()
    if not transcript:
        raise AppError("empty_transcript", "The transcript is empty", 422)
    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        raise AppError(
            "transcript_too_long",
            f"Transcripts are limited to {MAX_TRANSCRIPT_CHARS:,} characters",
            422,
        )
    title = (title or "").strip() or f"Meeting summary — {_today()}"
    return await run_tool(
        db,
        ai,
        user,
        GenerationKind.meeting,
        MEETING_QUERY,
        title=title,
        input_data={"title": title, "transcript_chars": len(transcript)},
        transcript=transcript,
        ip=ip,
    )


async def report(
    db: AsyncSession, ai: AIGateway, user: User, data: ReportRequest, ip: str | None
) -> Generation:
    doc_ids = list(dict.fromkeys(data.doc_ids or []))
    await ensure_visible(db, user, doc_ids)
    query = (
        f"Write a {data.report_type} report for the period: {data.period.strip()}.\n\n"
        f"Instructions: {data.instruction.strip()}"
    )
    return await run_tool(
        db,
        ai,
        user,
        GenerationKind.report,
        query,
        title=f"{data.report_type.title()} report — {data.period.strip()}",
        input_data=data.model_dump(mode="json"),
        doc_ids=doc_ids,
        ip=ip,
    )


async def email(
    db: AsyncSession, ai: AIGateway, user: User, data: EmailRequest, ip: str | None
) -> Generation:
    query = f"Task: {data.task}\nTone: {data.tone or 'professional'}\n\n{data.text.strip()}"
    return await run_tool(
        db,
        ai,
        user,
        GenerationKind.email,
        query,
        title="Email",
        input_data=data.model_dump(mode="json"),
        ip=ip,
    )


async def document_insights(
    db: AsyncSession, ai: AIGateway, user: User, document_id: uuid.UUID, ip: str | None
) -> Generation:
    doc = await get_visible(db, user, document_id)
    if doc.status is not DocumentStatus.ready:
        raise AppError(
            "document_not_ready", f"The document is {doc.status.value}, not ready yet", 409
        )
    return await run_tool(
        db,
        ai,
        user,
        GenerationKind.document_insights,
        f"Summarize and analyze this document: {doc.filename}",
        title=f"Insights — {doc.filename}",
        input_data={"document_id": str(doc.id), "filename": doc.filename},
        doc_ids=[doc.id],
        ip=ip,
    )


# --- transcript files ---------------------------------------------------------------------

_VTT_TIMING = re.compile(r"^\d{1,2}:?\d{2}:\d{2}[.,]\d{3}\s+-->\s+")
_VTT_VOICE = re.compile(r"<v(?:\.[^ >]*)?\s+([^>]+)>")
_TAGS = re.compile(r"</?[^>]+>")


def vtt_to_text(vtt: str) -> str:
    """WebVTT (Teams/Zoom exports) → 'Speaker: text' lines; drops headers, cue ids, timings."""
    out: list[str] = []
    for block in re.split(r"\n\s*\n", vtt.replace("\r\n", "\n")):
        lines = [ln.strip() for ln in block.strip().split("\n") if ln.strip()]
        if not lines or lines[0].startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        timing = next((i for i, ln in enumerate(lines) if _VTT_TIMING.match(ln)), None)
        text_lines = lines[timing + 1 :] if timing is not None else lines
        for ln in text_lines:
            speaker = _VTT_VOICE.search(ln)
            text = _TAGS.sub("", ln).strip()
            if text:
                out.append(f"{speaker.group(1).strip()}: {text}" if speaker else text)
    return "\n".join(out)


def _docx_text(data: bytes) -> str:
    from docx import Document as DocxDocument

    doc = DocxDocument(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


async def transcript_from_file(file: UploadFile) -> str:
    ext = PurePosixPath(file.filename or "").suffix.lower().lstrip(".")
    if ext not in TRANSCRIPT_EXTENSIONS:
        raise AppError(
            "unsupported_file_type", "Transcripts must be .txt, .vtt or .docx files", 400
        )
    data = await read_upload(file, MAX_TRANSCRIPT_FILE_BYTES)
    if ext == "docx":
        try:
            return await asyncio.to_thread(_docx_text, data)
        except Exception as exc:
            raise AppError(
                "invalid_file", "This doesn't look like a valid .docx file", 400
            ) from exc
    text = data.decode("utf-8-sig", errors="replace")
    return vtt_to_text(text) if ext == "vtt" else text


# --- generations ------------------------------------------------------------------------------


async def list_generations(
    db: AsyncSession,
    user: User,
    kind: GenerationKind | None,
    cursor: str | None,
    limit: int,
) -> tuple[list[Generation], str | None]:
    stmt = select(Generation).where(Generation.user_id == user.id, Generation.org_id == user.org_id)
    if kind:
        stmt = stmt.where(Generation.kind == kind)
    rows = list(
        (
            await db.scalars(paginate(stmt, Generation.created_at, Generation.id, cursor, limit))
        ).all()
    )
    return rows, next_cursor_for(rows, limit)


async def get_owned(db: AsyncSession, user: User, generation_id: uuid.UUID) -> Generation:
    gen = await db.scalar(
        select(Generation).where(
            Generation.id == generation_id,
            Generation.user_id == user.id,
            Generation.org_id == user.org_id,
        )
    )
    if gen is None:
        raise AppError("not_found", "Not found", 404)
    return gen


_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(text: str, fallback: str = "document") -> str:
    return _SLUG.sub("-", text.lower()).strip("-")[:80] or fallback


async def pdf_for(ai: AIGateway, gen: Generation) -> tuple[bytes, str]:
    markdown = gen.markdown or render(gen.kind, gen.output, gen.title)
    return await ai.export_pdf(markdown, gen.title), f"{slugify(gen.title)}.pdf"
