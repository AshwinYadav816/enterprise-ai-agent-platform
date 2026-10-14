"""Public facade. The backend imports ONLY this module (plus schemas for the types).

Contract:
    await ingest_document(file_bytes, filename, meta) -> IngestResult
    await delete_document(doc_id, org_id) -> None
    async for event in run(request): ...            # Event stream, forward as SSE
    await summarize_history(messages) -> str

Event stream for run() (forward each one as an SSE `data:` line):
    status "Planning…" -> status "Plan: meeting → email"
    per step: agent {name, step, total, instruction} -> that agent's events
              (status / sources / token / result, or error)
    [token events of a short wrap-up when the plan has more than one step]
    done {answer, agents, errors}
"result" events carry structured output (email, meeting summary, report…) for UI cards.
The stream never raises; failures become "error" events and "done" is always last.

Chat history: the backend owns it. When history exceeds 12 messages, call
summarize_history() on the older ones and send history_summary + the last 6 messages.
"""

import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from eap_ai import llm
from eap_ai.ingestion.pipeline import ingest
from eap_ai.orchestrator.graph import build_graph
from eap_ai.schemas import AgentRequest, ChatMessage, DocMeta, Event, IngestResult
from eap_ai.vectorstore import qdrant

log = logging.getLogger(__name__)

SUMMARY_MAX_WORDS = 150

SUMMARY_SYSTEM = f"""You summarize a conversation between a user and an assistant so it \
can continue later without the full transcript.
Keep: the user's goals, key facts and figures stated, decisions, open questions, and which \
documents were discussed. Drop greetings and filler.
Write plain prose in at most {SUMMARY_MAX_WORDS} words. Do not invent anything."""


class HistorySummary(BaseModel):
    summary: str = Field(description=f"Conversation summary, at most {SUMMARY_MAX_WORDS} words")


async def ingest_document(file_bytes: bytes, filename: str, meta: DocMeta) -> IngestResult:
    """Parse, chunk, embed and index a document (re-ingesting the same doc_id replaces it).

    Raises UnsupportedFileType for extensions other than pdf/docx/pptx/xlsx.
    """
    return await ingest(file_bytes, filename, meta)


async def delete_document(doc_id: str, org_id: str) -> None:
    """Remove every chunk of a document within the given org."""
    await qdrant.delete_by_doc(doc_id, org_id)


async def run(req: AgentRequest) -> AsyncIterator[Event]:
    """Route the request to agents and stream Events. Never raises; always ends with "done"."""
    final: dict[str, Any] = {}
    try:
        async for mode, chunk in build_graph().astream(
            {"request": req}, stream_mode=["custom", "values"]
        ):
            if mode == "custom":
                yield Event.model_validate(chunk)
            else:
                final = chunk
    except Exception:
        log.exception("run() failed for user %s", req.user.user_id)
        yield Event(type="error", data={"message": "Something went wrong while answering."})
    outputs = final.get("outputs", [])
    yield Event(
        type="done",
        data={
            "answer": final.get("final_text", ""),
            "agents": [o.get("agent") for o in outputs],
            "errors": sum("error" in o for o in outputs),
        },
    )


def _cap_words(text: str, limit: int) -> str:
    words = text.split()
    return text.strip() if len(words) <= limit else " ".join(words[:limit]) + "…"


async def summarize_history(messages: Sequence[ChatMessage]) -> str:
    """Rolling summary of older chat turns (fast model, at most 150 words)."""
    if not messages:
        return ""
    transcript = "\n".join(f"{m.role}: {m.content}" for m in messages)
    model = llm.get_chat_model("fast").with_structured_output(HistorySummary)
    result = await model.ainvoke(
        [SystemMessage(content=SUMMARY_SYSTEM), HumanMessage(content=transcript)]
    )
    assert isinstance(result, HistorySummary)
    return _cap_words(result.summary, SUMMARY_MAX_WORDS)
