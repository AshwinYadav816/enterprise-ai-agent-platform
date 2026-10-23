"""Document agent: summary, key points, entities and questions for selected documents."""

import asyncio
from collections.abc import AsyncIterator

from pydantic import BaseModel, Field

from eap_ai.agents.base import (
    UNTRUSTED_NOTE,
    AgentContext,
    AgentInputError,
    ask,
    count_tokens,
    partials_json,
    result_event,
    split_tokens,
    status_event,
    wrap,
)
from eap_ai.config import get_settings
from eap_ai.schemas import AgentName, Event
from eap_ai.vectorstore import qdrant


class DocumentInsights(BaseModel):
    summary: str
    key_points: list[str] = Field(default_factory=list)
    entities: list[str] = Field(
        default_factory=list, description="People, organisations, products, places, key dates"
    )
    questions_to_ask: list[str] = Field(
        default_factory=list, description="Useful follow-up questions the reader could ask"
    )


INSIGHTS_SYSTEM = f"""You analyze business documents.
Return: a concise summary (4-8 sentences), the key points, the important entities, and \
3-5 useful questions a reader could ask about the document.
Use only the document text; never invent facts. {UNTRUSTED_NOTE}"""

MAP_SYSTEM = f"""You extract notes from ONE PART of a longer document.
Return a short summary of this part, its key points and entities, and questions it raises.
Use only this text; never invent facts. {UNTRUSTED_NOTE}"""

REDUCE_SYSTEM = f"""You merge notes from consecutive parts of the same document set into one \
analysis: a concise overall summary (4-8 sentences), deduplicated key points and entities, \
and the 3-5 most useful questions. Never add facts not in the notes. {UNTRUSTED_NOTE}"""


async def _load_text(ctx: AgentContext) -> str:
    req = ctx.request
    if not req.doc_ids:
        raise AgentInputError("Please select at least one document to analyze.")
    blocks: list[str] = []
    for doc_id in req.doc_ids:
        records = await qdrant.scroll_doc(doc_id, req.user.org_id, req.user.roles)
        texts = [str((r.payload or {}).get("text", "")) for r in records]
        if texts:
            blocks.append("\n".join(texts))
    if not blocks:
        raise AgentInputError("No readable content found in the selected documents.")
    return "\n\n".join(blocks)


async def run(ctx: AgentContext) -> AsyncIterator[Event]:
    yield status_event("Reading the selected documents…")
    text = await _load_text(ctx)
    s = get_settings()
    request = f"Request: {ctx.instruction}\n\n"
    if await asyncio.to_thread(count_tokens, text) <= s.long_input_tokens:
        yield status_event("Analyzing…")
        insights = await ask(
            "document", DocumentInsights, INSIGHTS_SYSTEM, request + wrap("document", text)
        )
    else:
        parts = await asyncio.to_thread(split_tokens, text, s.map_chunk_tokens)
        partials: list[DocumentInsights] = []
        for i, part in enumerate(parts, start=1):
            yield status_event(f"Reading part {i} of {len(parts)}…")
            user = f"Part {i} of {len(parts)}.\n\n" + wrap("document", part)
            partials.append(await ask("map", DocumentInsights, MAP_SYSTEM, user))
        yield status_event("Merging notes…")
        insights = await ask(
            "document", DocumentInsights, REDUCE_SYSTEM, request + partials_json(partials)
        )
    yield result_event(AgentName.document, insights, doc_ids=list(ctx.request.doc_ids or []))
