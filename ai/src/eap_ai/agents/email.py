"""Email agent: draft, rewrite, fix grammar, change tone, or summarize a thread."""

from collections.abc import AsyncIterator
from enum import StrEnum

from pydantic import BaseModel, Field

from eap_ai.agents.base import (
    UNTRUSTED_NOTE,
    AgentContext,
    ask,
    format_prior_outputs,
    result_event,
    sources_event,
    status_event,
    wrap,
)
from eap_ai.rag.prompts import format_sources
from eap_ai.rag.retriever import retrieve
from eap_ai.schemas import AgentName, Event


class EmailTask(StrEnum):
    draft = "draft"
    rewrite = "rewrite"
    grammar = "grammar"
    tone = "tone"
    summarize_thread = "summarize_thread"


class EmailIntent(BaseModel):
    task: EmailTask
    tone: str = Field(description="Desired tone, e.g. professional, friendly, formal, concise")
    uses_documents: bool = Field(
        description="True only if the user refers to their uploaded documents/files/policies"
    )


class EmailOutput(BaseModel):
    subject: str
    body: str
    notes: str = Field(
        default="", description="Short notes for the user: assumptions, missing info, placeholders"
    )


CLASSIFY_SYSTEM = """Classify an email request.
task: draft (write a new email), rewrite (restructure/improve an existing email), grammar \
(fix spelling and grammar only), tone (change the tone of an existing email), \
summarize_thread (summarize an email thread).
tone: the tone the user wants; default "professional".
uses_documents: true only if the user asks to use their documents, files or policies."""

WRITE_SYSTEM = f"""You are an expert business email writer.
Produce the email for the given task:
- draft: write a complete email from the request and any provided material.
- rewrite / tone: keep every fact of the original email; change structure or tone as asked.
- grammar: fix only spelling, grammar and punctuation; keep wording otherwise.
- summarize_thread: the body is a short summary of the thread with decisions and next steps; \
the subject starts with "Summary:".
Rules:
- Use only facts from the request, earlier step outputs and documents provided.
- Never invent names, dates, numbers, deadlines, requests or commitments. Keep owners exactly \
as given ("Unassigned" stays unassigned). Use placeholders like [Name] and list them in notes.
- Be concise: short paragraphs or bullet lists, no filler such as "I hope this finds you well".
- Write the body as plain text (no Markdown bold), ending with a sign-off and [Your name].
- When documents are provided, you may cite them as [n].
- {UNTRUSTED_NOTE}"""


async def run(ctx: AgentContext) -> AsyncIterator[Event]:
    req = ctx.request
    yield status_event("Understanding the email request…")
    request_text = (
        ctx.instruction
        if ctx.instruction == req.query
        else (f"{ctx.instruction}\n\nOriginal user message:\n{req.query}")
    )
    intent = await ask("classify", EmailIntent, CLASSIFY_SYSTEM, request_text)

    parts = [f"Task: {intent.task.value}\nTone: {intent.tone}", wrap("document", request_text)]
    if prior := format_prior_outputs(ctx.prior_outputs):
        parts.append(prior)
    if intent.uses_documents:
        sources = await retrieve(ctx.instruction, req.user, req.doc_ids)
        if sources:
            yield sources_event(sources)
            parts.append("Documents:\n" + format_sources(sources))

    yield status_event("Writing the email…")
    email = await ask("email", EmailOutput, WRITE_SYSTEM, "\n\n".join(parts))
    yield result_event(AgentName.email, email, task=intent.task.value, tone=intent.tone)
