"""Backend ↔ AI module integration (Backend plan Part D checkpoints), with NO Mistral calls.

The REAL eap_ai code runs (orchestrator, agents, ingestion, retrieval, Qdrant in memory, PDF
engine); only its chat model and embedder are swapped for the AI module's own test fakes.
If either team changes the contract (event shapes, fields, roles), these tests fail.
"""

import importlib.util
import json
import sys
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pymupdf
import pytest
from eap_ai import cache as ai_cache
from eap_ai import llm as ai_llm
from eap_ai import service as ai_service
from eap_ai.agents.email import EmailIntent, EmailOutput, EmailTask
from eap_ai.agents.meeting import ActionItem, MeetingSummary
from eap_ai.agents.report import Report, ReportSection, ReportType
from eap_ai.orchestrator.state import Plan, Step
from eap_ai.schemas import AgentName, AgentRequest, ChatMessage, DocMeta, UserCtx
from eap_ai.service import HistorySummary
from eap_ai.vectorstore import qdrant as ai_qdrant
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Message, User, UserRole
from app.services.ai_gateway import FakeAIGateway, RealAIGateway, get_ai
from tests.factories import make_user

pytestmark = pytest.mark.filterwarnings("ignore:Payload indexes have no effect")

API = "/api/v1"
PASSWORD = "correct-horse-battery"
AI_TESTS = Path(__file__).resolve().parents[2] / "ai" / "tests" / "fakes.py"
USAGE = {"input_tokens": 40, "output_tokens": 10, "total_tokens": 50}


def _ai_fakes() -> Any:
    """The AI module's own fake chat model / embedder (single source of truth for fakes)."""
    spec = importlib.util.spec_from_file_location("eap_ai_test_fakes", AI_TESTS)
    assert spec and spec.loader, AI_TESTS
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


fakes = _ai_fakes()


@dataclass
class Models:
    fast: Any
    smart: Any


@pytest.fixture
async def real_ai(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Models]:
    monkeypatch.setenv("AI_MODE", "real")
    monkeypatch.setenv("REDIS_URL", "")  # AI embedding cache: in-process
    monkeypatch.setenv("SCORE_THRESHOLD", "-1")  # fake vectors: keep every hit
    from eap_ai.config import get_settings as get_ai_settings

    get_ai_settings.cache_clear()
    get_settings.cache_clear()
    ai_llm.clear_caches()
    await ai_cache.reset_cache()
    await ai_qdrant.close_client()

    models = Models(
        fast=fakes.FakeChatModel(model_name="fake-fast", usage=USAGE),
        smart=fakes.FakeChatModel(
            text="The hotel limit is 150 USD per night [1].", model_name="fake-smart", usage=USAGE
        ),
    )
    embedder = fakes.FakeEmbedder()
    monkeypatch.setattr(ai_llm, "get_embedder", lambda: embedder)
    monkeypatch.setattr(
        ai_llm,
        "get_chat_model",
        lambda task, streaming=False: (
            models.fast if ai_llm.tier_of(task) == "fast" else models.smart
        ),
    )
    app.dependency_overrides[get_ai] = lambda: RealAIGateway()
    yield models
    await ai_qdrant.close_client()
    await ai_cache.reset_cache()
    ai_llm.clear_caches()


def plan(*steps: tuple[AgentName, bool]) -> Plan:
    return Plan(
        steps=[Step(agent=a, instruction=f"do {a.value}", uses_previous=u) for a, u in steps],
        reason="test",
    )


def pdf_bytes(*pages: str) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def pdf_text(data: bytes) -> str:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    frames = []
    for block in body.split("\n\n"):
        if block.strip() and not block.startswith(":"):
            lines = dict(line.split(": ", 1) for line in block.split("\n"))
            frames.append((lines["event"], json.loads(lines["data"])))
    return frames


def shape(kinds: list[str]) -> list[str]:
    """Collapse runs of token/status events: their count differs, the shape must not."""
    return [
        k for i, k in enumerate(kinds) if not (k in ("token", "status") and i and kinds[i - 1] == k)
    ]


async def login(client: httpx.AsyncClient, user: User) -> dict[str, str]:
    r = await client.post(f"{API}/auth/login", json={"email": user.email, "password": PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- checkpoint 1: the contract -----------------------------------------------------------


async def test_contract_fake_gateway_matches_real_ai(real_ai: Models) -> None:
    """The backend's FakeAIGateway (used by every other test) must emit what eap_ai emits."""
    user = UserCtx(user_id="u", org_id=str(uuid.uuid4()), roles=["employee"])
    real_ai.fast.structured[Plan] = plan((AgentName.research, False))
    real_ai.fast.structured[EmailIntent] = EmailIntent(
        task=EmailTask.draft, tone="formal", uses_documents=False
    )
    real_ai.smart.structured[MeetingSummary] = MeetingSummary(summary="s")
    real_ai.smart.structured[EmailOutput] = EmailOutput(subject="S", body="B")
    real_ai.smart.structured[Report] = Report(report_type=ReportType.weekly, title="T", period="P")
    meta = DocMeta(
        doc_id=str(uuid.uuid4()), org_id=user.org_id, owner_id="u", allowed_roles=["employee"]
    )
    await ai_service.ingest_document(pdf_bytes("Sprint 7: beta shipped."), "status.pdf", meta)
    forced = (None, AgentName.chat, AgentName.meeting, AgentName.email, AgentName.report)
    for force in forced:
        req = AgentRequest(query="q", user=user, force_agent=force, transcript="A: hi")
        real = [e async for e in RealAIGateway().run(req)]
        fake = [e async for e in FakeAIGateway().run(req)]

        assert shape([e.type for e in real]) == shape([e.type for e in fake]), force
        assert set(real[-1].data) == set(fake[-1].data) == {"answer", "agents", "errors", "usage"}
        assert set(real[-1].data["usage"]) == set(fake[-1].data["usage"])
        real_result, fake_result = real[-2].data, fake[-2].data
        assert set(fake_result) <= set(real_result) and real_result["agent"] == fake_result["agent"]
        assert set(real_result["output"]) >= set(fake_result["output"])  # fake's fields are real
        assert {e.data["name"] for e in real if e.type == "agent"} == {
            e.data["name"] for e in fake if e.type == "agent"
        }

    # roles the backend sends: "system" carries the previous summary into summarize_history
    real_ai.fast.structured[HistorySummary] = HistorySummary(summary="ok")
    msgs = [
        ChatMessage(role="system", content="Summary so far: x"),
        ChatMessage(role="user", content="y"),
    ]
    assert await RealAIGateway().summarize_history(msgs) == "ok"
    assert (await RealAIGateway().health()) == {"config": "ok", "qdrant": "ok"}


# --- checkpoints 2–4 through the backend API -------------------------------------------------


async def test_upload_ready_vectors_then_cited_streaming_chat(
    real_ai: Models, client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """CP2: upload → ready → vectors in Qdrant. CP3: real streaming chat with citations."""
    user = await make_user(db, role=UserRole.manager, password=PASSWORD)
    h = await login(client, user)
    up = await client.post(
        f"{API}/documents",
        headers=h,
        files={
            "file": ("travel.pdf", pdf_bytes("Hotel limit is 150 USD per night.", "Meals 40 USD."))
        },
        data={"visibility": "manager"},
    )
    doc = (await client.get(f"{API}/documents/{up.json()['id']}", headers=h)).json()
    assert doc["status"] == "ready" and doc["chunk_count"] == 2 and doc["page_count"] == 2

    vectors = await ai_qdrant.scroll_doc(doc["id"], str(user.org_id), ["employee", "manager"])
    assert len(vectors) == 2 and vectors[0].payload["allowed_roles"] == ["manager"]
    assert await ai_qdrant.scroll_doc(doc["id"], str(user.org_id), ["employee"]) == []  # RBAC

    real_ai.fast.structured[Plan] = plan((AgentName.research, False))
    conv = (await client.post(f"{API}/conversations", headers=h)).json()["id"]
    r = await client.post(
        f"{API}/conversations/{conv}/messages", headers=h, json={"content": "Hotel limit?"}
    )
    frames = parse_sse(r.text)
    kinds = shape([k for k, _ in frames])
    assert kinds == ["status", "agent", "sources", "token", "result", "done"]  # runs collapsed
    sources = next(d for k, d in frames if k == "sources")["sources"]
    assert sources[0]["filename"] == "travel.pdf" and sources[0]["doc_id"] == doc["id"]
    done = frames[-1][1]
    assert done["answer"] == "The hotel limit is 150 USD per night [1]."
    saved = await db.get(Message, uuid.UUID(done["message_id"]))
    assert saved is not None and saved.agent == "research"
    assert saved.prompt_tokens > 0 and saved.completion_tokens > 0  # real usage reached the DB


async def test_meeting_to_email_chain_in_chat_and_pdfs(
    real_ai: Models, client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """CP4: "summarize this meeting and email the action items" in chat → both results → PDFs."""
    user = await make_user(db, password=PASSWORD)
    h = await login(client, user)
    real_ai.fast.structured[Plan] = plan((AgentName.meeting, False), (AgentName.email, True))
    real_ai.fast.structured[EmailIntent] = EmailIntent(
        task=EmailTask.draft, tone="professional", uses_documents=False
    )
    real_ai.smart.structured[MeetingSummary] = MeetingSummary(
        summary="Launch moved to 17 Sept.",
        key_decisions=["Move launch to 17 Sept"],
        action_items=[ActionItem(task="Update roadmap", owner="Rohit", due_date="Friday")],
    )
    real_ai.smart.structured[EmailOutput] = EmailOutput(
        subject="Launch action items", body="Hi team,\nRohit: update roadmap by Friday."
    )
    conv = (await client.post(f"{API}/conversations", headers=h)).json()["id"]
    r = await client.post(
        f"{API}/conversations/{conv}/messages",
        headers=h,
        json={
            "content": "Summarize this meeting and email the action items to the team",
            "transcript": (
                "Meera: move launch to 17 Sept.\nRohit: I'll update the roadmap by Friday."
            ),
        },
    )
    frames = parse_sse(r.text)
    assert [d["name"] for k, d in frames if k == "agent"] == ["meeting", "email"]
    email_prompt = next(inp for s, inp in real_ai.smart.structured_calls if s is EmailOutput)
    assert "Update roadmap" in email_prompt[1].content  # meeting output reached the email agent
    message_id = frames[-1][1]["message_id"]

    base = f"{API}/conversations/{conv}/messages/{message_id}/results"
    meeting_pdf = await client.get(f"{base}/0/pdf", headers=h)
    email_pdf = await client.get(f"{base}/1/pdf", headers=h)
    assert meeting_pdf.status_code == email_pdf.status_code == 200
    assert "Rohit" in pdf_text(meeting_pdf.content) and "Action items" in pdf_text(
        meeting_pdf.content
    )
    assert "Launch action items" in pdf_text(email_pdf.content)  # real fpdf2 rendering


async def test_report_tool_pdf_with_real_engine(
    real_ai: Models, client: httpx.AsyncClient, db: AsyncSession
) -> None:
    user = await make_user(db, password=PASSWORD)
    h = await login(client, user)
    await client.post(  # a report is only written from documents
        f"{API}/documents",
        headers=h,
        files={"file": ("sprint.pdf", pdf_bytes("Sprint 7: beta shipped. Vendor delay."))},
    )
    real_ai.smart.structured[Report] = Report(
        report_type=ReportType.sprint,
        title="Sprint 7 report",
        period="1–14 Oct",
        sections=[ReportSection(heading="Progress", content_md="Beta shipped.")],
        risks=["Vendor delay"],
    )
    gen = await client.post(
        f"{API}/tools/reports",
        headers=h,
        json={"report_type": "sprint", "period": "1–14 Oct", "instruction": "Mobile app"},
    )
    assert gen.status_code == 201 and gen.json()["title"] == "Sprint 7 report"
    assert gen.json()["markdown"].startswith("# Sprint 7 report")  # the AI's own markdown
    pdf = await client.get(f"{API}/tools/generations/{gen.json()['id']}/pdf", headers=h)
    text = pdf_text(pdf.content)
    assert "Sprint 7 report" in text and "Vendor delay" in text and "Page 1 of 1" in text


async def test_ready_includes_ai_checks_in_real_mode(
    real_ai: Models, client: httpx.AsyncClient, db: AsyncSession
) -> None:
    r = await client.get(f"{API}/ready")
    assert r.status_code == 200
    assert r.json()["checks"] == {
        "database": "ok",
        "redis": "ok",
        "ai_config": "ok",
        "qdrant": "ok",
    }
