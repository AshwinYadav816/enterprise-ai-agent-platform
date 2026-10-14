"""Public facade. The backend imports ONLY this module (plus schemas for the types).

Contract:
    await ingest_document(file_bytes, filename, meta) -> IngestResult
    await delete_document(doc_id, org_id) -> None
    async for event in run(request): ...            # Event stream, forward as SSE
    await summarize_history(messages) -> str
    export_pdf(markdown, title) -> bytes            # sync, CPU-bound: call via asyncio.to_thread

Event stream for run() (forward each one as an SSE `data:` line):
    status "Planning…" -> status "Plan: meeting → email"
    per step: agent {name, step, total, instruction} -> that agent's events
              (status / sources / token / result, or error)
    [token events of a short wrap-up when the plan has more than one step]
    done {answer, agents, errors}
"result" events carry structured output (email, meeting summary, report…) for UI cards;
report and meeting results also carry "markdown", ready for export_pdf().
The stream never raises; failures become "error" events and "done" is always last.

Rolling chat summary (the backend owns history; this module is stateless):
    if len(history) > HISTORY_SUMMARY_TRIGGER (12):
        summary = await summarize_history(history[:-HISTORY_KEEP_RECENT])   # older turns
        send AgentRequest(history_summary=summary, history=history[-HISTORY_KEEP_RECENT:])
    HISTORY_KEEP_RECENT is 6. Store the summary and refresh it the same way as the chat grows
    (pass the previous summary as the first message so nothing is lost).
"""

import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from eap_ai import llm
from eap_ai.export.pdf import markdown_to_pdf
from eap_ai.ingestion.pipeline import ingest
from eap_ai.orchestrator.graph import build_graph
from eap_ai.schemas import AgentRequest, ChatMessage, DocMeta, Event, IngestResult
from eap_ai.vectorstore import qdrant

log = logging.getLogger(__name__)

SUMMARY_MAX_WORDS = 150
HISTORY_SUMMARY_TRIGGER = 12  # backend summarizes when history is longer than this
HISTORY_KEEP_RECENT = 6  # ...and then sends only the summary + this many recent messages

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


def export_pdf(markdown: str, title: str) -> bytes:
    """Render Markdown (e.g. a report or meeting result's "markdown") to an A4 PDF.

    Unicode-safe (bundled DejaVu fonts), with title header, generated date and page numbers.
    Raw HTML and images in the Markdown are not rendered. Synchronous and CPU-bound:
    from async code call `await asyncio.to_thread(export_pdf, markdown, title)`.
    """
    return markdown_to_pdf(markdown, title)
