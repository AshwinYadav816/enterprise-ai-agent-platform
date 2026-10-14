from collections.abc import Iterator

import pytest
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_mistralai import embeddings as mistral_embeddings
from pydantic import BaseModel, ValidationError

from eap_ai import llm
from eap_ai.schemas import AgentName, AgentRequest, Event, Source, UserCtx
from tests.fakes import FakeChatModel, FakeEmbedder


@pytest.fixture(autouse=True)
def _fresh_llm_caches(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # MistralAIEmbeddings downloads a HF tokenizer on init; force its offline fallback.
    def _no_download(*args: object, **kwargs: object) -> None:
        raise OSError("offline in tests")

    monkeypatch.setattr(mistral_embeddings.Tokenizer, "from_pretrained", _no_download)
    llm.clear_caches()
    yield


# --- llm.py ---------------------------------------------------------------


def test_chat_model_tiers_use_settings() -> None:
    fast = llm.get_chat_model("fast")
    smart = llm.get_chat_model("smart", streaming=True)
    assert isinstance(fast, ChatMistralAI) and isinstance(smart, ChatMistralAI)
    assert fast.model == "ministral-8b-latest"
    assert smart.model == "ministral-14b-latest"
    assert smart.streaming is True and fast.streaming is False
    assert fast.max_retries == 2 and fast.timeout == 60


def test_chat_model_is_cached() -> None:
    assert llm.get_chat_model("fast") is llm.get_chat_model("fast")
    assert llm.get_chat_model("fast") is not llm.get_chat_model("fast", streaming=True)


def test_reasoning_effort_only_when_supported() -> None:
    fast = llm.get_chat_model("fast")
    if llm._supports_reasoning_effort():
        assert fast.reasoning_effort == "none"  # type: ignore[attr-defined]
    else:
        assert "reasoning_effort" not in fast.model_kwargs


def test_embedder_config_and_cache() -> None:
    emb = llm.get_embedder()  # fixture makes any HuggingFace download raise
    assert isinstance(emb, MistralAIEmbeddings)
    assert len(emb.tokenizer.encode_batch(["three word text"])[0]) == 3  # offline word count
    assert emb.model == "mistral-embed"
    assert emb.max_retries == 3 and emb.timeout == 60  # 3 attempts = 2 retries
    assert llm.get_embedder() is emb


async def test_embedding_dim_computed_once(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeEmbedder()
    monkeypatch.setattr(llm, "get_embedder", lambda: fake)
    assert await llm.embedding_dim() == 64
    assert await llm.embedding_dim() == 64
    assert fake.calls == 1


# --- fakes ------------------------------------------------------------------


class Answer(BaseModel):
    value: str


async def test_fake_chat_structured_output_in_order() -> None:
    model = FakeChatModel(structured={Answer: [Answer(value="a"), Answer(value="b")]})
    runnable = model.with_structured_output(Answer)
    assert await runnable.ainvoke("q1") == Answer(value="a")
    assert await runnable.ainvoke("q2") == Answer(value="b")
    assert await runnable.ainvoke("q3") == Answer(value="b")  # last one repeats
    assert len(model.structured_calls) == 3


async def test_fake_chat_streams_preset_text() -> None:
    model = FakeChatModel(text="Hello grounded world [1]")
    chunks = [c.content async for c in model.astream("hi")]
    assert len(chunks) > 1
    assert "".join(chunks) == "Hello grounded world [1]"
    assert (await model.ainvoke("hi")).content == "Hello grounded world [1]"


def test_fake_embedder_deterministic_and_similar() -> None:
    emb = FakeEmbedder()
    a = emb.embed_query("leave policy for employees")
    assert a == emb.embed_query("leave policy for employees")
    assert len(a) == 64

    def cos(x: list[float], y: list[float]) -> float:
        return sum(i * j for i, j in zip(x, y, strict=True))

    related = emb.embed_query("employees leave policy days")
    unrelated = emb.embed_query("quarterly revenue spreadsheet")
    assert cos(a, related) > cos(a, unrelated)


# --- schemas ----------------------------------------------------------------


def test_schemas_contract() -> None:
    req = AgentRequest(
        query="summarize",
        user=UserCtx(user_id="u1", org_id="o1", roles=["hr"]),
        force_agent="meeting",
    )
    assert req.force_agent is AgentName.meeting
    assert req.history == [] and req.doc_ids is None
    assert Event(type="token", data={"text": "hi"}).type == "token"
    with pytest.raises(ValidationError):
        Event(type="bogus")
    assert Source(n=1, doc_id="d", filename="f.pdf", snippet="s").page is None
