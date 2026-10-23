import hashlib
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest

from eap_ai import llm, service
from eap_ai.agents.base import AgentContext
from eap_ai.agents.chat import CHAT_SYSTEM
from eap_ai.agents.email import EmailIntent, EmailOutput, EmailTask
from eap_ai.agents.meeting import ActionItem, MeetingSummary
from eap_ai.orchestrator import graph
from eap_ai.orchestrator.state import Plan, Step
from eap_ai.schemas import AgentName, AgentRequest, ChatMessage, DocMeta, Event, UserCtx
from eap_ai.vectorstore import qdrant
from eap_ai.vectorstore.qdrant import ChunkRecord
from tests.fakes import FakeChatModel, FakeEmbedder

pytestmark = pytest.mark.filterwarnings("ignore:Payload indexes have no effect")

HR = UserCtx(user_id="u1", org_id="org1", roles=["hr"])
TRANSCRIPT = "Asha: Ship the beta Friday. Ravi: Asha will update the release notes by Thursday."
SUMMARY = MeetingSummary(
    summary="Beta ships Friday.",
    key_decisions=["Ship beta Friday"],
    action_items=[ActionItem(task="Update release notes", owner="Asha", due_date="Thursday")],
)
WRAP_UP = "Summarized the meeting and drafted the email."


@dataclass
class Models:
    fast: FakeChatModel
    smart: FakeChatModel
    embedder: FakeEmbedder


@pytest.fixture
async def models(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Models]:
    monkeypatch.setenv("QDRANT_URL", ":memory:")
    monkeypatch.setenv("SCORE_THRESHOLD", "-1")
    m = Models(
        fast=FakeChatModel(
            structured={
                EmailIntent: EmailIntent(
                    task=EmailTask.draft, tone="friendly", uses_documents=False
                )
            }
        ),
        smart=FakeChatModel(
            text="Employees get 24 days of leave [1].",
            structured={
                MeetingSummary: SUMMARY,
                EmailOutput: EmailOutput(subject="Action items", body="Asha: release notes."),
            },
        ),
        embedder=FakeEmbedder(),
    )
    llm.clear_caches()
    monkeypatch.setattr(llm, "get_embedder", lambda: m.embedder)
    monkeypatch.setattr(
        llm,
        "get_chat_model",
        lambda task, streaming=False: m.fast if llm.tier_of(task) == "fast" else m.smart,
    )
    await qdrant.close_client()
    yield m
    await qdrant.close_client()


def _plan(*steps: tuple[AgentName, bool]) -> Plan:
    return Plan(
        steps=[Step(agent=a, instruction=f"do {a.value}", uses_previous=u) for a, u in steps],
        reason="test",
    )


async def _run(**req: object) -> list[Event]:
    request = AgentRequest(user=HR, **{"query": "help me", **req})  # type: ignore[arg-type]
    return [e async for e in service.run(request)]


async def _seed() -> None:
    text = "[policy.pdf — p.1] Leave policy: 24 days of annual leave."
    vectors = await llm.get_embedder().aembed_documents([text])
    meta = DocMeta(doc_id="policy", org_id="org1", owner_id="o", allowed_roles=["hr"])
    chunk = ChunkRecord(text, 1, 0, hashlib.sha256(text.encode()).hexdigest())
    await qdrant.upsert_chunks(meta, "policy.pdf", [chunk], vectors)


def _done(events: list[Event]) -> dict[str, object]:
    """The done event's data without the usage block (covered in test_cache.py)."""
    assert events[-1].type == "done" and "usage" in events[-1].data
    return {k: v for k, v in events[-1].data.items() if k != "usage"}


def _types(events: list[Event]) -> list[str]:
    return [e.type for e in events]


def _statuses(events: list[Event]) -> list[str]:
    return [e.data["message"] for e in events if e.type == "status"]


def _plan_calls(models: Models) -> list[object]:
    return [inp for schema, inp in models.fast.structured_calls if schema is Plan]


# --- happy paths -----------------------------------------------------------------------


async def test_single_step_research(models: Models) -> None:
    await _seed()
    models.fast.structured[Plan] = _plan((AgentName.research, False))
    events = await _run(query="How many leave days?")

    types = _types(events)
    assert types[:3] == ["status", "status", "agent"]
    assert _statuses(events)[:2] == ["Planning…", "Plan: research"]
    assert types[3] == "sources" and types[-2:] == ["result", "done"]
    assert set(types[4:-2]) == {"token"}
    assert events[2].data == {
        "name": "research",
        "step": 1,
        "total": 1,
        "instruction": "do research",
    }
    assert "Wrapping up…" not in _statuses(events)  # no synthesis for one step
    assert _done(events) == {
        "answer": "Employees get 24 days of leave [1].",
        "agents": ["research"],
        "errors": 0,
    }


async def test_two_step_meeting_then_email(models: Models) -> None:
    models.fast.structured[Plan] = _plan((AgentName.meeting, False), (AgentName.email, True))
    models.smart.text = WRAP_UP
    events = await _run(query="Summarize and email the team", transcript=TRANSCRIPT)

    agents = [e.data["name"] for e in events if e.type == "agent"]
    assert agents == ["meeting", "email"]
    results = [e.data["agent"] for e in events if e.type == "result"]
    assert results == ["meeting", "email"]

    # the meeting's action items reach the email agent
    email_prompt = next(inp for s, inp in models.smart.structured_calls if s is EmailOutput)
    assert '<prior_output agent="meeting">' in email_prompt[1].content
    assert "Update release notes" in email_prompt[1].content

    # synthesis streams after the last result, then done
    last_result = max(i for i, e in enumerate(events) if e.type == "result")
    tail = _types(events)[last_result + 1 :]
    assert tail[0] == "status" and set(tail[1:-1]) == {"token"} and tail[-1] == "done"
    assert _done(events) == {"answer": WRAP_UP, "agents": ["meeting", "email"], "errors": 0}


async def test_force_agent_skips_router(models: Models) -> None:
    events = await _run(query="Summarize", transcript=TRANSCRIPT, force_agent="meeting")
    assert _plan_calls(models) == []  # router LLM never called
    assert _done(events) == {"answer": "Beta ships Friday.", "agents": ["meeting"], "errors": 0}


async def test_chat_uses_summary_without_retrieval(models: Models) -> None:
    models.fast.structured[Plan] = _plan((AgentName.chat, False))
    models.smart.text = "Hi! How can I help?"
    history = [
        ChatMessage(role="user", content="hello"),
        ChatMessage(role="assistant", content="hi"),
    ]
    events = await _run(query="thanks!", history=history, history_summary="User likes brevity.")
    assert models.embedder.calls == 0
    (messages,) = models.smart.calls
    assert messages[0].content == CHAT_SYSTEM  # system prompt stays static
    assert [m.content for m in messages[1:3]] == ["hello", "hi"]
    assert messages[3].content.startswith("<conversation>\nUser likes brevity.\n</conversation>")
    assert messages[3].content.endswith("thanks!")
    assert events[-1].data["answer"] == "Hi! How can I help?"


async def test_router_sees_transcript_and_doc_flags(models: Models) -> None:
    models.fast.structured[Plan] = _plan((AgentName.chat, False))
    await _run(query="Summarize this file", doc_ids=["a", "b"])
    (prompt,) = _plan_calls(models)
    content = prompt[1].content  # type: ignore[index]
    assert "Transcript attached: no" in content and "Selected documents: 2" in content


# --- plan validation -------------------------------------------------------------------


async def test_plan_clamped_to_three_steps(models: Models) -> None:
    models.fast.structured[Plan] = _plan(*[(AgentName.chat, False)] * 5)
    events = await _run()
    assert [e.data["total"] for e in events if e.type == "agent"] == [3, 3, 3]


async def test_router_failure_falls_back_to_research(models: Models) -> None:
    # no Plan preset -> the fake raises -> router falls back to research
    events = await _run(query="anything")
    assert events[-1].data["agents"] == ["research"]
    assert "Plan: research" in _statuses(events)


# --- errors ----------------------------------------------------------------------------


async def test_failing_step_reports_error_and_continues(
    models: Models, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(ctx: AgentContext) -> AsyncIterator[Event]:
        raise RuntimeError("database password=hunter2")
        yield  # pragma: no cover

    monkeypatch.setitem(graph.AGENTS, AgentName.report, broken)
    models.fast.structured[Plan] = _plan(
        (AgentName.report, False), (AgentName.chat, False), (AgentName.email, True)
    )
    models.smart.text = WRAP_UP
    events = await _run()

    errors = [e.data for e in events if e.type == "error"]
    assert errors[0] == {"agent": "report", "message": "The report step failed. Please try again."}
    assert errors[1]["agent"] == "email" and "Skipped" in errors[1]["message"]
    assert all("hunter2" not in e["message"] for e in errors)  # no internals leaked
    assert [e.data["agent"] for e in events if e.type == "result"] == ["chat"]  # independent ran
    assert events[-1].type == "done" and events[-1].data["errors"] == 2
    synth_prompt = models.smart.calls[-1][1].content
    assert "Failed steps:" in synth_prompt and "report" in synth_prompt


async def test_provider_busy_gets_a_clear_message(
    models: Models, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def busy(ctx: AgentContext) -> AsyncIterator[Event]:
        request = httpx.Request("POST", "https://api.mistral.ai/v1/embeddings")
        raise httpx.HTTPStatusError("429", request=request, response=httpx.Response(429))
        yield  # pragma: no cover

    monkeypatch.setitem(graph.AGENTS, AgentName.research, busy)
    events = await _run(query="How many sick days?", force_agent="research")
    (error,) = [e for e in events if e.type == "error"]
    assert error.data["message"] == graph.PROVIDER_BUSY
    assert events[-1].data["answer"] == graph.PROVIDER_BUSY


async def test_agent_input_error_message_is_shown(models: Models) -> None:
    events = await _run(query="Summarize the meeting", force_agent="meeting")  # no transcript
    (error,) = [e for e in events if e.type == "error"]
    assert error.data["message"] == "Please provide a meeting transcript to summarize."
    assert events[-1].type == "done" and events[-1].data["errors"] == 1


async def test_synthesis_failure_keeps_step_results(
    models: Models, monkeypatch: pytest.MonkeyPatch
) -> None:
    models.fast.structured[Plan] = _plan((AgentName.chat, False), (AgentName.chat, False))
    real_stream = FakeChatModel._astream
    calls = {"n": 0}

    async def flaky(self: FakeChatModel, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 3:  # the two chat steps succeed, the wrap-up fails
            raise RuntimeError("model down")
        async for chunk in real_stream(self, *args, **kwargs):  # type: ignore[arg-type]
            yield chunk

    monkeypatch.setattr(FakeChatModel, "_astream", flaky)
    events = await _run()
    assert [e.data["agent"] for e in events if e.type == "result"] == ["chat", "chat"]
    (error,) = [e for e in events if e.type == "error"]
    assert error.data["message"] == "Could not write the final summary."
    assert events[-1].type == "done" and events[-1].data["answer"] == "Done: chat, chat."
