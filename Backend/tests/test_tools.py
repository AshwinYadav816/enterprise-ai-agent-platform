import io
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from docx import Document as DocxDocument
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    AuditLog,
    Document,
    DocumentStatus,
    Generation,
    GenerationKind,
    User,
    UserRole,
)
from app.services import audit
from app.services.ai_gateway import AgentRequest, Event, FakeAIGateway, get_ai
from app.services.markdown import render
from app.services.tools import slugify, vtt_to_text
from tests.factories import make_org, make_user

API = "/api/v1"
PASSWORD = "correct-horse-battery"
TRANSCRIPT = "Asha: Ship the beta on Friday.\nRavi: Asha will update the release notes."


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def login(
    client: httpx.AsyncClient, db: AsyncSession, **kw: object
) -> tuple[User, dict[str, str]]:
    user = await make_user(db, password=PASSWORD, **kw)  # type: ignore[arg-type]
    r = await client.post(f"{API}/auth/login", json={"email": user.email, "password": PASSWORD})
    return user, bearer(r.json()["access_token"])


async def make_doc(
    db: AsyncSession, user: User, status: DocumentStatus, roles: list[str]
) -> Document:
    doc = Document(
        org_id=user.org_id,
        owner_id=user.id,
        filename="roadmap.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key=f"{user.org_id}/x/roadmap.pdf",
        allowed_roles=roles,
        status=status,
    )
    db.add(doc)
    await db.flush()
    return doc


# --- meetings ------------------------------------------


async def test_meeting_from_json_saves_generation(
    client: httpx.AsyncClient, db: AsyncSession, fake_ai: FakeAIGateway
) -> None:
    user, h = await login(client, db)
    r = await client.post(
        f"{API}/tools/meetings", headers=h, json={"transcript": TRANSCRIPT, "title": "Launch sync"}
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "meeting" and body["title"] == "Launch sync"
    assert body["output"]["key_decisions"] == ["Ship on Friday"]
    assert body["output"]["action_items"][0]["owner"] == "Unassigned"
    assert body["markdown"].startswith("# Meeting summary")  # the AI's own markdown is kept
    assert (body["prompt_tokens"], body["completion_tokens"]) == (120, 30)
    assert body["input"] == {"title": "Launch sync", "transcript_chars": len(TRANSCRIPT)}

    (req,) = fake_ai.requests
    assert req.force_agent is not None and req.force_agent.value == "meeting"
    assert req.transcript == TRANSCRIPT and req.user.org_id == str(user.org_id)
    gen = await db.get(Generation, uuid.UUID(body["id"]))
    assert gen is not None and gen.user_id == user.id
    assert await db.scalar(select(AuditLog.id).where(AuditLog.action == audit.GENERATION_CREATED))


def _docx(text: str) -> bytes:
    d = DocxDocument()
    for line in text.split("\n"):
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


VTT = """WEBVTT

1
00:00:01.000 --> 00:00:04.000
<v Asha Rao>Ship the beta on Friday.</v>

2
00:00:04.500 --> 00:00:07.000
<v Ravi>Asha will update the release notes.
"""


@pytest.mark.parametrize(
    ("name", "data", "expected"),
    [
        ("notes.txt", TRANSCRIPT.encode(), TRANSCRIPT),
        (
            "call.vtt",
            VTT.encode(),
            "Asha Rao: Ship the beta on Friday.\nRavi: Asha will update the release notes.",
        ),
        ("minutes.docx", _docx(TRANSCRIPT), TRANSCRIPT),
    ],
    ids=["txt", "vtt", "docx"],
)
async def test_meeting_from_file(
    client: httpx.AsyncClient,
    db: AsyncSession,
    fake_ai: FakeAIGateway,
    name: str,
    data: bytes,
    expected: str,
) -> None:
    _, h = await login(client, db)
    r = await client.post(
        f"{API}/tools/meetings",
        headers=h,
        files={"file": (name, data)},
        data={"title": "From file"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["title"] == "From file"
    assert fake_ai.requests[-1].transcript == expected


@pytest.mark.parametrize(
    ("kwargs", "status", "code"),
    [
        ({"files": {"file": ("notes.pdf", b"%PDF")}}, 400, "unsupported_file_type"),
        ({"files": {"file": ("bad.docx", b"not a zip")}}, 400, "invalid_file"),
        (
            {"data": {"title": "no file"}, "files": {"other": ("x.txt", b"x")}},
            422,
            "validation_error",
        ),
        ({"json": {"transcript": "   "}}, 422, "empty_transcript"),
        ({"json": {"transcript": "x" * 200_001}}, 422, "validation_error"),
        (
            {"content": b"{not json", "headers": {"Content-Type": "application/json"}},
            422,
            "validation_error",
        ),
    ],
    ids=["pdf-file", "corrupt-docx", "no-file-field", "blank", "too-long", "bad-json"],
)
async def test_meeting_input_errors(
    client: httpx.AsyncClient, db: AsyncSession, kwargs: dict, status: int, code: str
) -> None:
    _, h = await login(client, db)
    headers = {**h, **kwargs.pop("headers", {})}
    r = await client.post(f"{API}/tools/meetings", headers=headers, **kwargs)
    assert r.status_code == status and r.json()["error"]["code"] == code


# --- reports / emails / insights ------------------------------------------


async def test_report_with_visible_docs(
    client: httpx.AsyncClient, db: AsyncSession, fake_ai: FakeAIGateway
) -> None:
    user, h = await login(client, db, role=UserRole.manager)
    doc = await make_doc(db, user, DocumentStatus.ready, ["manager"])
    r = await client.post(
        f"{API}/tools/reports",
        headers=h,
        json={
            "report_type": "sprint",
            "period": "Sprint 7",
            "instruction": "Cover the mobile app",
            "doc_ids": [str(doc.id)],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "report" and r.json()["title"] == "Weekly report"  # AI's title
    req = fake_ai.requests[-1]
    assert "sprint report for the period: Sprint 7" in req.query and "mobile app" in req.query
    assert req.doc_ids == [str(doc.id)]

    _, he = await login(client, db)  # a user in a different org
    hidden = await client.post(
        f"{API}/tools/reports",
        headers=he,
        json={
            "report_type": "weekly",
            "period": "W42",
            "instruction": "x",
            "doc_ids": [str(doc.id)],
        },
    )
    assert hidden.status_code == 404 and hidden.json()["error"]["code"] == "document_not_found"


async def test_email_query_and_markdown(
    client: httpx.AsyncClient, db: AsyncSession, fake_ai: FakeAIGateway
) -> None:
    _, h = await login(client, db)
    r = await client.post(
        f"{API}/tools/emails",
        headers=h,
        json={"task": "rewrite", "tone": "formal", "text": "hey team, launch is friday"},
    )
    assert r.status_code == 201
    assert fake_ai.requests[-1].query == "Task: rewrite\nTone: formal\n\nhey team, launch is friday"
    body = r.json()
    assert body["title"] == "Follow-up"  # the AI's subject
    assert body["markdown"].startswith("# Follow-up\n") and "launch is friday" in body["markdown"]
    bad = await client.post(f"{API}/tools/emails", headers=h, json={"task": "poem", "text": "x"})
    assert bad.status_code == 422


async def test_document_insights_requires_visible_ready_doc(
    client: httpx.AsyncClient, db: AsyncSession, fake_ai: FakeAIGateway
) -> None:
    user, h = await login(client, db)
    processing = await make_doc(db, user, DocumentStatus.processing, ["employee"])
    ready = await make_doc(db, user, DocumentStatus.ready, ["employee"])
    secret = await make_doc(db, user, DocumentStatus.ready, ["admin"])

    r = await client.post(f"{API}/tools/documents/{processing.id}/insights", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "document_not_ready"
    r = await client.post(f"{API}/tools/documents/{secret.id}/insights", headers=h)
    assert r.status_code == 404
    r = await client.post(f"{API}/tools/documents/{ready.id}/insights", headers=h)
    assert r.status_code == 201 and r.json()["title"] == "Insights — roadmap.pdf"
    assert fake_ai.requests[-1].doc_ids == [str(ready.id)]
    assert r.json()["markdown"].startswith("# Insights — roadmap.pdf")


# --- AI failures ------------------------------------------


class NoResult(FakeAIGateway):
    async def run(self, req: AgentRequest) -> AsyncIterator[Event]:
        yield Event(type="done", data={"answer": "", "agents": [], "errors": 0})


class StepError(FakeAIGateway):
    async def run(self, req: AgentRequest) -> AsyncIterator[Event]:
        yield Event(
            type="error",
            data={
                "agent": "meeting",
                "message": "Please provide a meeting transcript to summarize.",
            },
        )
        yield Event(type="done", data={"answer": "", "agents": ["meeting"], "errors": 1})


class Raises(FakeAIGateway):
    async def run(self, req: AgentRequest) -> AsyncIterator[Event]:
        raise RuntimeError("mistral key sk-secret rejected")
        yield  # pragma: no cover


@pytest.mark.parametrize(
    ("gateway", "message"),
    [
        (NoResult(), "AI could not complete this request"),
        (
            StepError(),
            "AI could not complete this request: Please provide a meeting transcript to summarize.",
        ),
        (Raises(), "AI could not complete this request"),
    ],
    ids=["no-result", "step-error", "raises"],
)
async def test_ai_failures_are_502_and_nothing_saved(
    app: FastAPI, client: httpx.AsyncClient, db: AsyncSession, gateway: FakeAIGateway, message: str
) -> None:
    app.dependency_overrides[get_ai] = lambda: gateway
    _, h = await login(client, db)
    r = await client.post(f"{API}/tools/meetings", headers=h, json={"transcript": TRANSCRIPT})
    assert r.status_code == 502 and r.json()["error"] == {"code": "ai_failed", "message": message}
    assert "sk-secret" not in r.text
    assert await db.scalar(select(Generation.id)) is None


async def test_tools_are_rate_limited(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_PER_MIN", "1")
    get_settings.cache_clear()
    _, h = await login(client, db)
    body = {"task": "draft", "text": "hello"}
    assert (await client.post(f"{API}/tools/emails", headers=h, json=body)).status_code == 201
    assert (await client.post(f"{API}/tools/emails", headers=h, json=body)).status_code == 429


# --- generations + PDF ------------------------------------------


async def test_generations_list_detail_pdf_and_ownership(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    org = await make_org(db)
    _, h = await login(client, db, org=org)
    meeting = (
        await client.post(
            f"{API}/tools/meetings",
            headers=h,
            json={"transcript": TRANSCRIPT, "title": "Q3 Launch / Sync!"},
        )
    ).json()
    await client.post(f"{API}/tools/emails", headers=h, json={"task": "draft", "text": "hi"})

    listed = (await client.get(f"{API}/tools/generations", headers=h)).json()
    assert [g["kind"] for g in listed["items"]] == ["email", "meeting"]  # newest first
    assert "output" not in listed["items"][0]  # list stays light
    only = (
        await client.get(f"{API}/tools/generations", headers=h, params={"kind": "meeting"})
    ).json()
    assert [g["id"] for g in only["items"]] == [meeting["id"]]

    detail = await client.get(f"{API}/tools/generations/{meeting['id']}", headers=h)
    assert detail.status_code == 200 and detail.json()["output"] == meeting["output"]
    pdf = await client.get(f"{API}/tools/generations/{meeting['id']}/pdf", headers=h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"].startswith(
        'attachment; filename="q3-launch-sync.pdf"'
    )

    _, colleague = await login(client, db, org=org)  # same org, different user
    for path in ("", "/pdf"):
        r = await client.get(f"{API}/tools/generations/{meeting['id']}{path}", headers=colleague)
        assert r.status_code == 404
    assert (await client.get(f"{API}/tools/generations", headers=colleague)).json()["items"] == []


# --- pure helpers ------------------------------------------


def test_markdown_render_each_kind() -> None:
    meeting = render(
        GenerationKind.meeting,
        {
            "summary": "Launch moved.",
            "key_decisions": ["Move to 17 Sep"],
            "action_items": [
                {"task": "Update | roadmap", "owner": "Rohit", "due_date": "Friday"},
                {"task": "Tell marketing", "owner": None, "due_date": None},
            ],
            "open_questions": ["Budget?"],
        },
        "Launch sync",
    )
    assert meeting.splitlines()[:3] == ["# Launch sync", "", "Launch moved."]
    assert "| Update \\| roadmap | Rohit | Friday |" in meeting
    assert "| Tell marketing | Unassigned | — |" in meeting
    assert (
        "## Key decisions\n- Move to 17 Sep" in meeting
        and "## Open questions\n- Budget?" in meeting
    )

    report = render(
        GenerationKind.report,
        {
            "report_type": "sprint",
            "title": "Sprint 7",
            "period": "1–14 Oct",
            "sections": [{"heading": "Progress", "content_md": "Beta shipped [1]."}],
            "highlights": ["Beta"],
            "risks": ["Vendor delay"],
            "next_steps": ["Launch"],
        },
    )
    assert report.startswith("# Sprint 7\n\n*Sprint report — 1–14 Oct*")
    for line in (
        "## Highlights",
        "## Progress",
        "Beta shipped [1].",
        "## Risks",
        "- Vendor delay",
        "## Next steps",
    ):
        assert line in report

    email = render(
        GenerationKind.email, {"subject": "Hi", "body": "Body text", "notes": "Fill [Name]"}
    )
    assert email == "# Hi\n\nBody text\n\n---\n\n*Notes: Fill [Name]*\n"

    insights = render(
        GenerationKind.document_insights,
        {"summary": "S.", "key_points": ["k"], "entities": ["Acme"], "questions_to_ask": ["Q?"]},
    )
    assert (
        insights.startswith("# Document insights\n\nS.") and "## Questions to ask\n- Q?" in insights
    )


def test_vtt_and_slug_helpers() -> None:
    assert vtt_to_text(VTT).splitlines() == [
        "Asha Rao: Ship the beta on Friday.",
        "Ravi: Asha will update the release notes.",
    ]
    assert slugify("Q3 Launch / Sync!") == "q3-launch-sync" and slugify("---") == "document"
