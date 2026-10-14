"""Public facade. The backend imports ONLY this module (plus schemas for the types).

Contract:
    await ingest_document(file_bytes, filename, meta) -> IngestResult
    await delete_document(doc_id, org_id) -> None
    async for event in run(request): ...            # Event stream, forward as SSE
    await summarize_history(messages) -> str

Event stream for run(): "sources" -> "token"* -> "done", or an "error" event if
something fails. The stream never raises.
"""

import logging
from collections.abc import AsyncIterator, Sequence

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from eap_ai import llm
from eap_ai.ingestion.pipeline import ingest
from eap_ai.rag.answer import answer_stream
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
    """Answer a request as a stream of Events. Temporary: RAG only (orchestrator in phase 6)."""
    try:
        async for event in answer_stream(req.query, req.user, req.history, req.doc_ids):
            yield event
    except Exception:
        log.exception("run() failed for user %s", req.user.user_id)
        yield Event(type="error", data={"message": "Something went wrong while answering."})


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
