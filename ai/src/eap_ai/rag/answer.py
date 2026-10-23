"""Grounded answering: sources event -> streamed tokens -> done."""

import logging
import re
from collections.abc import AsyncIterator, Sequence

from langchain_core.messages import HumanMessage, SystemMessage

from eap_ai import llm
from eap_ai.rag.prompts import ANSWER_SYSTEM, NOT_FOUND, NOT_FOUND_REPLY, answer_user_message
from eap_ai.rag.retriever import retrieve, rewrite_query
from eap_ai.schemas import ChatMessage, Event, Source, UserCtx

log = logging.getLogger(__name__)

SNIPPET_PREVIEW_CHARS = 300
_CITATION = re.compile(r"\[(\d+)\]")


def cited_numbers(answer: str, n_sources: int) -> list[int]:
    """Source numbers actually cited as [n] in the answer, so the UI can highlight them."""
    return sorted({n for m in _CITATION.findall(answer) if 1 <= (n := int(m)) <= n_sources})


def _sources_event(sources: Sequence[Source]) -> Event:
    preview = [
        s.model_copy(update={"snippet": s.snippet[:SNIPPET_PREVIEW_CHARS]}).model_dump()
        for s in sources
    ]
    return Event(type="sources", data={"sources": preview})


async def answer_stream(
    query: str,
    user: UserCtx,
    history: Sequence[ChatMessage] = (),
    doc_ids: Sequence[str] | None = None,
) -> AsyncIterator[Event]:
    standalone = await rewrite_query(query, history)
    sources = await retrieve(standalone, user, doc_ids)
    yield _sources_event(sources)

    if not sources:  # nothing relevant: answer without paying for an LLM call
        yield Event(type="token", data={"text": NOT_FOUND_REPLY})
        yield Event(type="done", data={"answer": NOT_FOUND_REPLY, "found": False, "cited": []})
        return

    messages = [
        SystemMessage(content=ANSWER_SYSTEM),
        HumanMessage(content=answer_user_message(standalone, sources)),
    ]
    parts: list[str] = []
    async for chunk in llm.get_chat_model("answer", streaming=True).astream(messages):
        text = chunk.content if isinstance(chunk.content, str) else ""
        if text:
            parts.append(text)
            yield Event(type="token", data={"text": text})
    answer = "".join(parts)
    cited = cited_numbers(answer, len(sources))
    found = NOT_FOUND not in answer
    if found and not cited:
        # The model answered without citing any source: treat it as made up and refuse instead.
        # The final answer (shown and saved) replaces the streamed tokens.
        log.warning("Uncited answer replaced with not-found (%d sources)", len(sources))
        answer, found = NOT_FOUND_REPLY, False
    yield Event(type="done", data={"answer": answer, "found": found, "cited": cited})
