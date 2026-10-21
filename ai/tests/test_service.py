import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pymupdf
import pytest

from dev_api import app
from eap_ai import llm, service
from eap_ai.config import get_settings
from eap_ai.orchestrator.state import Plan, Step
from eap_ai.rag.retriever import StandaloneQuestion
from eap_ai.schemas import AgentName, AgentRequest, ChatMessage, DocMeta, Event, UserCtx
from eap_ai.service import SUMMARY_MAX_WORDS, HistorySummary
from eap_ai.vectorstore import qdrant
from tests.fakes import FakeChatModel, FakeEmbedder

pytestmark = pytest.mark.filterwarnings("ignore:Payload indexes have no effect")

HR = UserCtx(user_id="u1", org_id="org1", roles=["hr"])


@pytest.fixture
async def chat(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[FakeChatModel]:
    monkeypatch.setenv("QDRANT_URL", ":memory:")
    monkeypatch.setenv("SCORE_THRESHOLD", "-1")
    embedder = FakeEmbedder()
    model = FakeChatModel(
        text="Employees get 24 days of leave [1].",
        structured={
            HistorySummary: HistorySummary(summary="User asked about leave; 24 days per year."),
            StandaloneQuestion: StandaloneQuestion(question="how many leave days"),
            Plan: Plan(steps=[Step(agent=AgentName.research, instruction="leave days?")]),
        },
    )
    llm.clear_caches()
    monkeypatch.setattr(llm, "get_embedder", lambda: embedder)
    monkeypatch.setattr(llm, "get_chat_model", lambda tier, streaming=False: model)
    await qdrant.close_client()
    yield model
    await qdrant.close_client()


def _pdf(text: str) -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


async def _events(req: AgentRequest) -> list[Event]:
    return [e async for e in service.run(req)]


# --- service facade --------------------------------------------------------------


async def test_ingest_run_delete_round_trip(chat: FakeChatModel) -> None:
    meta = DocMeta(doc_id="d1", org_id="org1", owner_id="u1", allowed_roles=["hr"])
    result = await service.ingest_document(_pdf("Leave policy: 24 days per year."), "p.pdf", meta)
    assert result.chunks == 1 and result.pages == 1

    events = await _events(AgentRequest(query="leave days?", user=HR))
    sources = next(e for e in events if e.type == "sources")
    assert sources.data["sources"][0]["doc_id"] == "d1"
    assert events[-1].type == "done" and events[-1].data["agents"] == ["research"]

    await service.delete_document("d1", "org1")
    events = await _events(AgentRequest(query="leave days?", user=HR))
    result = next(e for e in events if e.type == "result")
    assert result.data["output"]["sources"] == [] and result.data["output"]["found"] is False


async def test_run_never_raises(chat: FakeChatModel, monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(*args: object, **kwargs: object) -> list[float]:
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(llm.get_embedder(), "aembed_query", boom)
    events = await _events(AgentRequest(query="anything", user=HR))
    errors = [e for e in events if e.type == "error"]
    assert len(errors) == 1 and events[-1].type == "done" and events[-1].data["errors"] == 1
    assert "qdrant down" not in errors[0].data["message"]  # no internals leaked


async def test_summarize_history(chat: FakeChatModel) -> None:
    msgs = [
        ChatMessage(role="user", content="How much leave do I get?"),
        ChatMessage(role="assistant", content="24 days per year [1]."),
    ]
    assert await service.summarize_history(msgs) == "User asked about leave; 24 days per year."
    ((schema, prompt),) = chat.structured_calls
    assert schema is HistorySummary and "24 days per year" in prompt[1].content


async def test_summarize_history_caps_words_and_skips_empty(chat: FakeChatModel) -> None:
    chat.structured[HistorySummary] = HistorySummary(summary="word " * 400)
    msgs = [ChatMessage(role="user", content="hi")]
    summary = await service.summarize_history(msgs)
    assert len(summary.split()) == SUMMARY_MAX_WORDS
    chat.structured_calls.clear()
    assert await service.summarize_history([]) == ""
    assert chat.structured_calls == []


# --- dev API ------------------------------------------------------------------------


@pytest.fixture
async def client(chat: FakeChatModel) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


HEADERS = {"X-User-Id": "u1", "X-Org-Id": "org1", "X-Roles": "hr, employee"}


def _sse(body: str) -> list[dict[str, Any]]:
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


def _first(events: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    return next(e for e in events if e["type"] == kind)


async def test_api_ingest_chat_delete(client: httpx.AsyncClient) -> None:
    files = {"file": ("policy.pdf", _pdf("Leave policy: 24 days per year."), "application/pdf")}
    r = await client.post(
        "/ingest", files=files, data={"allowed_roles": "hr", "doc_id": "d1"}, headers=HEADERS
    )
    assert r.status_code == 200, r.text
    assert r.json()["doc_id"] == "d1" and r.json()["chunks"] == 1

    r = await client.post("/chat", json={"query": "leave days?"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _sse(r.text)
    assert _first(events, "sources")["data"]["sources"][0]["doc_id"] == "d1"
    assert events[-1]["type"] == "done"
    assert events[-1]["data"]["answer"] == "Employees get 24 days of leave [1]."

    # another org (from headers) cannot see it
    other = {**HEADERS, "X-Org-Id": "org2"}
    r = await client.post("/chat", json={"query": "leave days?"}, headers=other)
    assert _first(_sse(r.text), "sources")["data"]["sources"] == []

    assert (await client.delete("/docs/d1", headers=HEADERS)).status_code == 204
    r = await client.post("/chat", json={"query": "leave days?"}, headers=HEADERS)
    assert _first(_sse(r.text), "result")["data"]["output"]["found"] is False


async def test_api_rejects_unsupported_and_empty_roles(client: httpx.AsyncClient) -> None:
    txt = {"file": ("notes.txt", b"hello", "text/plain")}
    r = await client.post("/ingest", files=txt, data={"allowed_roles": "hr"}, headers=HEADERS)
    assert r.status_code == 415
    pdf = {"file": ("p.pdf", _pdf("x"), "application/pdf")}
    r = await client.post("/ingest", files=pdf, data={"allowed_roles": " , "}, headers=HEADERS)
    assert r.status_code == 422


async def test_api_generates_doc_id_and_uses_header_defaults(client: httpx.AsyncClient) -> None:
    files = {"file": ("p.pdf", _pdf("Remote work two days a week."), "application/pdf")}
    r = await client.post("/ingest", files=files, data={"allowed_roles": "employee"})
    assert r.status_code == 200 and len(r.json()["doc_id"]) == 36  # uuid4
    assert (await client.get("/health")).json() == {"status": "ok"}


async def test_ingest_rejects_oversized_and_unsupported_before_parsing(
    chat: FakeChatModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    meta = DocMeta(doc_id="d", org_id="org1", owner_id="u1", allowed_roles=["hr"])
    with pytest.raises(service.FileTooLarge, match="1 MB"):
        await service.ingest_document(b"x" * (1024 * 1024 + 1), "big.pdf", meta)
    with pytest.raises(service.UnsupportedFileType):
        await service.ingest_document(b"hello", "notes.txt", meta)
    assert llm.get_embedder().calls == 0  # nothing parsed or embedded


async def test_api_maps_ingest_errors_to_http_codes(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    corrupt = {"file": ("bad.pdf", b"not a pdf", "application/pdf")}
    r = await client.post("/ingest", files=corrupt, data={"allowed_roles": "hr"}, headers=HEADERS)
    assert r.status_code == 422 and "damaged" in r.json()["detail"]
    monkeypatch.setenv("MAX_UPLOAD_MB", "0")
    get_settings.cache_clear()
    pdf = {"file": ("p.pdf", _pdf("x"), "application/pdf")}
    r = await client.post("/ingest", files=pdf, data={"allowed_roles": "hr"}, headers=HEADERS)
    assert r.status_code == 413


async def test_health_reports_qdrant_and_config(
    chat: FakeChatModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert await service.health() == {"config": "ok", "qdrant": "ok"}  # in-memory Qdrant

    class DownClient:
        async def get_collections(self) -> None:
            raise ConnectionError("qdrant down")

    monkeypatch.setattr(qdrant, "get_client", lambda: DownClient())
    assert await service.health() == {"config": "ok", "qdrant": "unavailable"}


async def test_health_reports_invalid_config(monkeypatch: pytest.MonkeyPatch) -> None:
    from eap_ai.config import get_settings

    monkeypatch.delenv("MISTRAL_API_KEY")
    get_settings.cache_clear()
    assert await service.health() == {"config": "invalid", "qdrant": "unknown"}
