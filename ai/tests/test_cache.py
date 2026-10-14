from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any

import httpx
import pymupdf
import pytest
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_mistralai import ChatMistralAI

from eap_ai import cache, llm, service
from eap_ai.cache import MemoryCache, RedisCache, embedding_key, get_cache, pack, unpack
from eap_ai.ingestion import pipeline
from eap_ai.orchestrator.state import Plan, Step
from eap_ai.rag.retriever import retrieve
from eap_ai.schemas import AgentName, AgentRequest, DocMeta, UserCtx
from eap_ai.service import usage_summary
from eap_ai.vectorstore import qdrant
from tests.fakes import FakeChatModel, FakeEmbedder

pytestmark = pytest.mark.filterwarnings("ignore:Payload indexes have no effect")

HR = UserCtx(user_id="u1", org_id="org1", roles=["hr"])
META = DocMeta(doc_id="d1", org_id="org1", owner_id="u1", allowed_roles=["hr"])
USAGE = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@dataclass
class Env:
    embedder: FakeEmbedder
    fast: FakeChatModel
    smart: FakeChatModel


@pytest.fixture
async def env(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Env]:
    monkeypatch.setenv("QDRANT_URL", ":memory:")
    monkeypatch.setenv("SCORE_THRESHOLD", "-1")
    e = Env(
        embedder=FakeEmbedder(),
        fast=FakeChatModel(model_name="fake-fast", usage=USAGE),
        smart=FakeChatModel(text="Answer [1].", model_name="fake-smart", usage=USAGE),
    )
    llm.clear_caches()
    monkeypatch.setattr(llm, "get_embedder", lambda: e.embedder)
    monkeypatch.setattr(
        llm, "get_chat_model", lambda tier, streaming=False: e.fast if tier == "fast" else e.smart
    )
    await qdrant.close_client()
    await llm.embedding_dim()  # one-time dimension probe, so counters below start clean
    e.embedder.calls = e.embedder.texts_embedded = 0
    yield e
    await qdrant.close_client()


def _pdf(*pages: str) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


# --- backends ------------------------------------------------------------------------


def test_pack_roundtrip_is_float32_compact() -> None:
    vec = [0.1, -0.25, 3.0]
    assert len(pack(vec)) == 12  # 4 bytes per float
    assert unpack(pack(vec)) == pytest.approx(vec, rel=1e-6)


async def test_memory_cache_lru_and_ttl() -> None:
    clock = Clock()
    c = MemoryCache(max_items=2, clock=clock)
    await c.set_many({"a": [1.0], "b": [2.0]}, ttl=None)
    assert await c.get_many(["a"]) == [[1.0]]  # touch a -> b is least recently used
    await c.set_many({"c": [3.0]}, ttl=None)
    assert await c.get_many(["a", "b", "c"]) == [[1.0], None, [3.0]]

    await c.set_many({"q": [9.0]}, ttl=60)
    clock.now += 59
    assert await c.get_many(["q"]) == [[9.0]]
    clock.now += 2
    assert await c.get_many(["q"]) == [None]  # expired


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.ttls: dict[str, int | None] = {}

    async def mget(self, keys: list[str]) -> list[bytes | None]:
        return [self.store.get(k) for k in keys]

    def pipeline(self, transaction: bool = True) -> "FakeRedis":
        return self

    async def __aenter__(self) -> "FakeRedis":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    def set(self, key: str, value: bytes, ex: int | None = None) -> None:
        self.store[key], self.ttls[key] = value, ex

    async def execute(self) -> None:
        return None

    async def aclose(self) -> None:
        return None


async def test_redis_cache_serializes_and_sets_ttl() -> None:
    rc = RedisCache.__new__(RedisCache)
    fake = FakeRedis()
    rc._redis = fake  # type: ignore[assignment]
    await rc.set_many({"doc": [1.0, 2.0]}, ttl=None)
    await rc.set_many({"query": [3.0]}, ttl=3600)
    assert fake.ttls == {"doc": None, "query": 3600}
    assert await rc.get_many(["doc", "missing", "query"]) == [[1.0, 2.0], None, [3.0]]


async def test_backend_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    from eap_ai.config import get_settings

    monkeypatch.setenv("REDIS_URL", "")  # empty in .env means "not set"
    get_settings.cache_clear()
    assert isinstance(get_cache(), MemoryCache)

    await cache.reset_cache()
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6399/0")  # client connects lazily
    get_settings.cache_clear()
    assert isinstance(get_cache(), RedisCache)
    await cache.reset_cache()


def test_key_depends_on_model_text_and_kind() -> None:
    base = embedding_key("hello", "doc", model="mistral-embed")
    assert base.startswith("eap:emb:doc:")
    assert base != embedding_key("hello", "doc", model="other-embed")
    assert base != embedding_key("hello!", "doc", model="mistral-embed")
    assert base != embedding_key("hello", "query", model="mistral-embed")


# --- (1) document embeddings: unchanged chunks are not re-embedded -------------------


async def test_reingest_same_file_makes_zero_embedding_calls(env: Env) -> None:
    data = _pdf("Leave policy: 24 days.", "Remote work: two days a week.")
    await pipeline.ingest(data, "policy.pdf", META)
    assert env.embedder.calls == 1 and env.embedder.texts_embedded == 2

    result = await pipeline.ingest(data, "policy.pdf", META)
    assert result.chunks == 2
    assert env.embedder.calls == 1  # nothing new sent to the API


async def test_reingest_changed_file_embeds_only_changed_chunks(env: Env) -> None:
    await pipeline.ingest(_pdf("Leave policy: 24 days.", "Remote work: two days."), "p.pdf", META)
    await pipeline.ingest(_pdf("Leave policy: 24 days.", "Remote work: three days."), "p.pdf", META)
    assert env.embedder.texts_embedded == 3  # 2 first time + 1 changed chunk


async def test_cache_failure_falls_back_to_embedding(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Broken:
        async def get_many(self, keys: Sequence[str]) -> list[Any]:
            raise ConnectionError("redis down")

        async def set_many(self, items: dict[str, list[float]], ttl: int | None) -> None:
            raise ConnectionError("redis down")

        async def close(self) -> None:
            return None

    monkeypatch.setattr(cache, "_cache", Broken())
    result = await pipeline.ingest(_pdf("Leave policy: 24 days."), "p.pdf", META)
    assert result.chunks == 1 and env.embedder.texts_embedded == 1


# --- (2) query embeddings with TTL ------------------------------------------------------


async def test_query_embedding_cached_until_ttl(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = Clock()
    monkeypatch.setattr(cache, "_cache", MemoryCache(100, clock=clock))
    await pipeline.ingest(_pdf("Leave policy: 24 days."), "p.pdf", META)
    env.embedder.calls = 0

    await retrieve("how many leave days?", HR)
    await retrieve("how many leave days?", HR)
    assert env.embedder.calls == 1  # second identical query served from cache

    clock.now += 3601  # past the 1h TTL
    await retrieve("how many leave days?", HR)
    assert env.embedder.calls == 2


# --- llm.py: retries with backoff --------------------------------------------------------


def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.mistral.ai/v1/chat/completions")
    return httpx.HTTPStatusError(
        f"Error response {code}", request=request, response=httpx.Response(code, request=request)
    )


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    recorded: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        recorded.append(seconds)

    monkeypatch.setattr(llm, "_sleep", fake_sleep)
    return recorded


def _model() -> llm.RetryingChatMistralAI:
    return llm.RetryingChatMistralAI(api_key="test", status_retries=2, retry_backoff=1.0)


def _patch_generate(monkeypatch: pytest.MonkeyPatch, failures: list[Exception]) -> list[int]:
    calls: list[int] = []

    async def fake(self: Any, messages: Any, **kwargs: Any) -> ChatResult:
        calls.append(1)
        if failures:
            raise failures.pop(0)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])

    monkeypatch.setattr(ChatMistralAI, "_agenerate", fake)
    return calls


async def test_retries_rate_limit_with_exponential_backoff(
    monkeypatch: pytest.MonkeyPatch, sleeps: list[float]
) -> None:
    calls = _patch_generate(monkeypatch, [_status_error(429), _status_error(503)])
    assert (await _model().ainvoke("hi")).content == "ok"
    assert len(calls) == 3
    assert 1.0 <= sleeps[0] < 1.5 and 2.0 <= sleeps[1] < 2.5  # 1s, 2s (+ jitter)


async def test_gives_up_after_two_retries_and_skips_client_errors(
    monkeypatch: pytest.MonkeyPatch, sleeps: list[float]
) -> None:
    calls = _patch_generate(monkeypatch, [_status_error(429)] * 5)
    with pytest.raises(httpx.HTTPStatusError):
        await _model().ainvoke("hi")
    assert len(calls) == 3

    calls = _patch_generate(monkeypatch, [_status_error(400)])
    with pytest.raises(httpx.HTTPStatusError):
        await _model().ainvoke("hi")
    assert len(calls) == 1  # bad request is never retried


async def test_stream_retries_only_before_first_chunk(
    monkeypatch: pytest.MonkeyPatch, sleeps: list[float]
) -> None:
    plan: list[str] = ["fail-early", "ok"]

    async def fake_stream(self: Any, messages: Any, **kwargs: Any) -> AsyncIterator[Any]:
        mode = plan.pop(0)
        if mode == "fail-early":
            raise _status_error(429)
        if mode == "fail-late":
            yield ChatGenerationChunk(message=AIMessageChunk(content="Hel"))
            raise _status_error(503)
        for tok in ("Hel", "lo"):
            yield ChatGenerationChunk(message=AIMessageChunk(content=tok))

    monkeypatch.setattr(ChatMistralAI, "_astream", fake_stream)
    text = "".join([c.content async for c in _model().astream("hi")])  # type: ignore[misc]
    assert text == "Hello" and len(sleeps) == 1

    plan[:] = ["fail-late", "ok"]
    with pytest.raises(httpx.HTTPStatusError):
        [c async for c in _model().astream("hi")]  # no retry: user already saw "Hel"


def test_clients_use_configured_timeouts_and_retries() -> None:
    llm.clear_caches()
    chat = llm.get_chat_model("smart")
    assert isinstance(chat, llm.RetryingChatMistralAI)
    assert chat.timeout == 60 and chat.status_retries == 2 and chat.max_retries == 2
    emb = llm.get_embedder()
    assert emb.timeout == 60 and emb.max_retries == 3  # type: ignore[attr-defined]


# --- token usage on the done event ---------------------------------------------------------


def test_usage_summary_totals_and_empty() -> None:
    u = usage_summary({"a": USAGE, "b": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}})
    assert (u["input_tokens"], u["output_tokens"], u["total_tokens"]) == (11, 7, 18)
    assert u["by_model"]["a"] == USAGE
    assert usage_summary({}) == {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "by_model": {},
    }


async def test_done_event_reports_usage_across_all_calls(env: Env) -> None:
    env.fast.structured[Plan] = Plan(
        steps=[
            Step(agent=AgentName.chat, instruction="hi"),
            Step(agent=AgentName.chat, instruction="hey"),
        ]
    )
    events = [e async for e in service.run(AgentRequest(query="hello", user=HR))]
    usage = events[-1].data["usage"]
    # 2 chat streams + 1 synthesis stream on the smart model, 15 tokens each
    assert usage["total_tokens"] == 45
    assert usage["by_model"] == {
        "fake-smart": {"input_tokens": 30, "output_tokens": 15, "total_tokens": 45}
    }


async def test_usage_present_even_when_nothing_ran(env: Env) -> None:
    events = [e async for e in service.run(AgentRequest(query="x", user=HR, force_agent="meeting"))]
    assert events[-1].type == "done" and events[-1].data["usage"]["total_tokens"] == 0
