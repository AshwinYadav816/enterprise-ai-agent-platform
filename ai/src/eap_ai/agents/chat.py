"""Chat agent: small talk and questions about the assistant. No retrieval."""

from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from eap_ai import llm
from eap_ai.agents.base import AgentContext, result_event
from eap_ai.schemas import AgentName, Event

CHAT_HISTORY_MESSAGES = 6

CHAT_SYSTEM = """You are the friendly assistant of an enterprise AI platform. You can answer \
questions from the user's uploaded documents, summarize documents and meetings, draft emails \
and write reports. Reply briefly and naturally. For questions about company facts, policies or \
data, do not answer from general knowledge: suggest asking about their documents instead."""


class ChatOutput(BaseModel):
    answer: str


async def run(ctx: AgentContext) -> AsyncIterator[Event]:
    req = ctx.request
    system = CHAT_SYSTEM
    if req.history_summary:
        system += f"\n\nSummary of the earlier conversation:\n{req.history_summary}"
    messages: list[BaseMessage] = [SystemMessage(content=system)]
    for m in req.history[-CHAT_HISTORY_MESSAGES:]:
        messages.append(
            AIMessage(content=m.content)
            if m.role == "assistant"
            else HumanMessage(content=m.content)
        )
    messages.append(HumanMessage(content=req.query))

    parts: list[str] = []
    async for chunk in llm.get_chat_model("smart", streaming=True).astream(messages):
        if isinstance(chunk.content, str) and chunk.content:
            parts.append(chunk.content)
            yield Event(type="token", data={"text": chunk.content})
    yield result_event(AgentName.chat, ChatOutput(answer="".join(parts)))
