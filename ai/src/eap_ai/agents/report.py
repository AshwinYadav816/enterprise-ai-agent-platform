"""Report agent: weekly / monthly / sprint / project reports from docs and earlier steps."""

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
)
from eap_ai.rag.prompts import format_sources
from eap_ai.rag.retriever import retrieve
from eap_ai.schemas import AgentName, Event


class ReportType(StrEnum):
    weekly = "weekly"
    monthly = "monthly"
    sprint = "sprint"
    project = "project"


class ReportSection(BaseModel):
    heading: str
    content_md: str = Field(description="Section body in Markdown")


class Report(BaseModel):
    report_type: ReportType
    title: str
    period: str = Field(
        description='Period covered as stated in the material, else "Not specified"'
    )
    sections: list[ReportSection] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            f"# {self.title}",
            "",
            f"*{self.report_type.value.title()} report — {self.period}*",
        ]
        if self.highlights:
            lines += ["", "## Highlights", *[f"- {i}" for i in self.highlights]]
        for section in self.sections:
            lines += ["", f"## {section.heading}", "", section.content_md.strip()]
        for heading, items in (("Risks", self.risks), ("Next steps", self.next_steps)):
            if items:
                lines += ["", f"## {heading}", *[f"- {i}" for i in items]]
        return "\n".join(lines) + "\n"


REPORT_SYSTEM = f"""You write clear, factual business reports.
report_type: weekly, monthly, sprint or project, from the user's request (default project).
Structure: 2-5 sections with Markdown content; highlights, risks and next steps as short items.
Rules: use only facts from the request, the documents and earlier step outputs; cite documents \
as [n]; never invent numbers, dates, names or progress. If material is thin, say so in a section \
called "Data gaps" rather than filling in. {UNTRUSTED_NOTE}"""


async def run(ctx: AgentContext) -> AsyncIterator[Event]:
    req = ctx.request
    yield status_event("Gathering material for the report…")
    parts = [f"Request: {ctx.instruction}"]
    sources = await retrieve(ctx.instruction, req.user, req.doc_ids)
    if sources:
        yield sources_event(sources)
        parts.append("Documents:\n" + format_sources(sources))
    if prior := format_prior_outputs(ctx.prior_outputs):
        parts.append(prior)
    if not sources and not ctx.prior_outputs:
        parts.append("No documents matched this request.")

    yield status_event("Writing the report…")
    report = await ask("smart", Report, REPORT_SYSTEM, "\n\n".join(parts))
    yield result_event(AgentName.report, report, markdown=report.to_markdown())
