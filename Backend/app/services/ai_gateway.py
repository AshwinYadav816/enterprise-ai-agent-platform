"""The only door to the AI module. Real mode calls eap_ai.service; fake mode needs no keys.

Types come from eap_ai.schemas (lightweight); eap_ai.service is imported lazily so the app
starts (and tests run) without Mistral/Qdrant configured.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from functools import lru_cache
from typing import Annotated, Any, Protocol

from eap_ai.schemas import (
    AgentName,
    AgentRequest,
    ChatMessage,
    DocMeta,
    Event,
    IngestResult,
    UserCtx,
)
from fastapi import Depends

from app.core.config import get_settings
from app.core.security import expand_roles
from app.models import User

log = logging.getLogger(__name__)

__all__ = [
    "AIGateway",
    "AIIngestError",
    "AgentName",
    "AgentRequest",
    "ChatMessage",
    "DocMeta",
    "Event",
    "FakeAIGateway",
    "IngestResult",
    "RealAIGateway",
    "UserCtx",
    "get_ai",
    "user_ctx",
]


class AIIngestError(Exception):
    """The document can't be ingested; the message is safe to show the user."""


class AIGateway(Protocol):
    async def ingest_document(
        self, file_bytes: bytes, filename: str, meta: DocMeta
    ) -> IngestResult: ...
    async def delete_document(self, doc_id: str, org_id: str) -> None: ...
    def run(self, req: AgentRequest) -> AsyncIterator[Event]: ...
    async def summarize_history(self, messages: Sequence[ChatMessage]) -> str: ...
    async def export_pdf(self, markdown: str, title: str) -> bytes: ...
    async def health(self) -> dict[str, str]: ...


def user_ctx(user: User) -> UserCtx:
    """The AI module's view of a user: roles expanded so retrieval sees what the role may see."""
    return UserCtx(user_id=str(user.id), org_id=str(user.org_id), roles=expand_roles(user.role))


# --- real ------------------------------------------------------------------------------------


class RealAIGateway:
    async def ingest_document(
        self, file_bytes: bytes, filename: str, meta: DocMeta
    ) -> IngestResult:
        from eap_ai import service

        try:
            return await service.ingest_document(file_bytes, filename, meta)
        except service.IngestError as exc:  # too large / unsupported / unreadable: user-safe
            raise AIIngestError(str(exc)) from exc

    async def delete_document(self, doc_id: str, org_id: str) -> None:
        from eap_ai import service

        await service.delete_document(doc_id, org_id)

    async def run(self, req: AgentRequest) -> AsyncIterator[Event]:
        from eap_ai import service

        async for event in service.run(req):
            yield event

    async def summarize_history(self, messages: Sequence[ChatMessage]) -> str:
        from eap_ai import service

        return await service.summarize_history(messages)

    async def export_pdf(self, markdown: str, title: str) -> bytes:
        from eap_ai import service

        return await asyncio.to_thread(service.export_pdf, markdown, title)  # CPU-bound

    async def health(self) -> dict[str, str]:
        from eap_ai import service

        return await service.health()


async def warm_up_ai() -> None:
    """Import eap_ai.service (~5 s: LangGraph, LangChain, Qdrant client) off the event loop at
    startup, so the first chat/upload after a restart doesn't pay for it."""
    import importlib

    try:
        await asyncio.to_thread(importlib.import_module, "eap_ai.service")
        log.info("AI module loaded")
    except Exception:
        log.exception("AI module failed to load; requests will retry the import")


# --- fake (local UI work and tests) --------------------------------------------------------------

# Smallest valid PDF: one empty page.
MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)

FAKE_USAGE = {
    "input_tokens": 120,
    "output_tokens": 30,
    "total_tokens": 150,
    "by_model": {"fake-model": {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}},
}


def _fake_output(agent: AgentName, query: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """(output, extra result fields) shaped like the real agents' results."""
    if agent is AgentName.meeting:
        out = {
            "summary": "The team agreed on next steps.",
            "key_decisions": ["Ship on Friday"],
            "action_items": [{"task": "Update notes", "owner": "Unassigned", "due_date": None}],
            "open_questions": [],
        }
        return out, {"markdown": "# Meeting summary\n\nThe team agreed on next steps.\n"}
    if agent is AgentName.email:
        out = {"subject": "Follow-up", "body": f"Hi team,\n\n{query}\n\n[Your name]", "notes": ""}
        return out, {"task": "draft", "tone": "professional"}
    if agent is AgentName.report:
        out = {
            "report_type": "weekly",
            "title": "Weekly report",
            "period": "Not specified",
            "sections": [{"heading": "Progress", "content_md": "Work continued."}],
            "highlights": [],
            "risks": [],
            "next_steps": [],
        }
        return out, {"markdown": "# Weekly report\n\n## Progress\n\nWork continued.\n"}
    if agent is AgentName.document:
        out = {
            "summary": "A short document.",
            "key_points": [],
            "entities": [],
            "questions_to_ask": [],
        }
        return out, {}
    if agent is AgentName.chat:
        return {"answer": "Hello! How can I help?"}, {}
    return {"answer": "This is a fake answer [1].", "found": True, "cited": [1], "sources": []}, {}


class FakeAIGateway:
    """Deterministic stand-in with the real event shape. Records calls for tests."""

    def __init__(self, *, ingest_error: Exception | None = None) -> None:
        self.ingest_error = ingest_error
        self.ingested: list[DocMeta] = []
        self.deleted: list[tuple[str, str]] = []
        self.requests: list[AgentRequest] = []

    async def ingest_document(
        self, file_bytes: bytes, filename: str, meta: DocMeta
    ) -> IngestResult:
        if self.ingest_error is not None:
            raise self.ingest_error
        self.ingested.append(meta)
        return IngestResult(chunks=3, pages=2, warnings=[])

    async def delete_document(self, doc_id: str, org_id: str) -> None:
        self.deleted.append((doc_id, org_id))

    async def run(self, req: AgentRequest) -> AsyncIterator[Event]:
        self.requests.append(req)
        agent = req.force_agent or AgentName.research
        yield Event(type="status", data={"message": "Planning…"})
        yield Event(type="status", data={"message": f"Plan: {agent.value}"})
        yield Event(
            type="agent",
            data={"name": agent.value, "step": 1, "total": 1, "instruction": req.query},
        )
        output, extra = _fake_output(agent, req.query)
        answer = output.get("answer") or output.get("summary") or output.get("body") or ""
        if agent in (AgentName.research, AgentName.chat):  # only these stream text
            if agent is AgentName.research:
                yield Event(type="sources", data={"sources": []})
            for word in answer.split(" "):
                yield Event(type="token", data={"text": word + " "})
        else:  # meeting/email/report/document: progress statuses, then the result card
            yield Event(type="status", data={"message": f"Working on the {agent.value}…"})
        yield Event(type="result", data={"agent": agent.value, "output": output, **extra})
        yield Event(
            type="done",
            data={"answer": answer, "agents": [agent.value], "errors": 0, "usage": FAKE_USAGE},
        )

    async def summarize_history(self, messages: Sequence[ChatMessage]) -> str:
        return f"Summary of {len(messages)} earlier messages."

    async def export_pdf(self, markdown: str, title: str) -> bytes:
        return MINIMAL_PDF

    async def health(self) -> dict[str, str]:
        return {"config": "ok", "qdrant": "ok"}


@lru_cache
def _real() -> RealAIGateway:
    return RealAIGateway()


@lru_cache
def _fake() -> FakeAIGateway:
    return FakeAIGateway()


def get_ai() -> AIGateway:
    return _real() if get_settings().ai_mode == "real" else _fake()


AI = Annotated[AIGateway, Depends(get_ai)]
