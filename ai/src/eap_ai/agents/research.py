"""Research agent: grounded Q&A over the user's documents (wraps the RAG answer stream)."""

from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field

from eap_ai.agents.base import AgentContext, result_event
from eap_ai.rag.answer import answer_stream
from eap_ai.schemas import AgentName, Event, Source


class ResearchOutput(BaseModel):
    answer: str
    found: bool
    cited: list[int] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)


async def run(ctx: AgentContext) -> AsyncIterator[Event]:
    req = ctx.request
    sources: list[dict[str, Any]] = []
    done: dict[str, Any] = {}
    async for event in answer_stream(ctx.instruction, req.user, req.history, req.doc_ids):
        if event.type == "done":  # the orchestrator owns the final "done"
            done = event.data
            continue
        if event.type == "sources":
            sources = event.data["sources"]
        yield event
    output = ResearchOutput(
        answer=done.get("answer", ""),
        found=bool(done.get("found", False)),
        cited=done.get("cited", []),
        sources=[Source(**s) for s in sources],
    )
    yield result_event(AgentName.research, output)
