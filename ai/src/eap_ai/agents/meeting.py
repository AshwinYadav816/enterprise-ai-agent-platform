"""Meeting agent: summary, decisions, action items and open questions from a transcript."""

import re
from collections.abc import AsyncIterator

from pydantic import BaseModel, Field

from eap_ai.agents.base import (
    UNTRUSTED_NOTE,
    AgentContext,
    AgentInputError,
    ask,
    count_tokens,
    format_prior_outputs,
    partials_json,
    result_event,
    split_tokens,
    status_event,
    wrap,
)
from eap_ai.config import get_settings
from eap_ai.schemas import AgentName, Event

UNASSIGNED = "Unassigned"


class ActionItem(BaseModel):
    task: str
    owner: str = Field(
        default=UNASSIGNED,
        description=f'Person named in the transcript as responsible, else "{UNASSIGNED}"',
    )
    due_date: str | None = Field(
        default=None, description="Deadline exactly as stated in the transcript, else null"
    )


class MeetingSummary(BaseModel):
    summary: str
    key_decisions: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    def to_markdown(self, title: str = "Meeting summary") -> str:
        def cell(text: str) -> str:
            return text.replace("|", "\\|").replace("\n", " ")

        lines = [f"# {title}", "", self.summary.strip()]
        if self.key_decisions:
            lines += ["", "## Key decisions", *[f"- {d}" for d in self.key_decisions]]
        if self.action_items:
            lines += ["", "## Action items", "", "| Task | Owner | Due |", "|---|---|---|"]
            lines += [
                f"| {cell(a.task)} | {cell(a.owner)} | {cell(a.due_date or '—')} |"
                for a in self.action_items
            ]
        if self.open_questions:
            lines += ["", "## Open questions", *[f"- {q}" for q in self.open_questions]]
        return "\n".join(lines) + "\n"


_RULES = f"""Rules:
- Use only what is said in the transcript. Never invent facts, names or dates.
- owner: only a person the transcript explicitly names as responsible; otherwise \
"{UNASSIGNED}". Never guess an owner from who spoke.
- due_date: only if a deadline is stated (keep its wording, e.g. "Friday"); otherwise null.
- {UNTRUSTED_NOTE}"""

SUMMARY_SYSTEM = f"""You summarize business meetings from transcripts.
Return: a concise summary (3-6 sentences), key decisions, action items, open questions.
{_RULES}"""

MAP_SYSTEM = f"""You extract notes from ONE PART of a longer meeting transcript.
Return: a short summary of this part, decisions, action items and open questions found in it.
{_RULES}"""

REDUCE_SYSTEM = f"""You merge partial notes from consecutive parts of one meeting into a \
single summary. Write one concise overall summary (3-6 sentences). Merge duplicate \
decisions, action items and questions; drop questions answered in a later part. Keep owners \
and due dates exactly as given in the partials; never add new ones.
{_RULES}"""


def _meeting_text(ctx: AgentContext) -> str:
    if ctx.request.transcript and ctx.request.transcript.strip():
        return ctx.request.transcript
    if prior := format_prior_outputs(ctx.prior_outputs):
        return prior
    raise AgentInputError("Please provide a meeting transcript to summarize.")


def _named_in(owner: str, transcript: str) -> bool:
    words = [w for w in re.findall(r"\w+", owner) if len(w) > 1]
    text = transcript.lower()
    return bool(words) and any(re.search(rf"\b{re.escape(w.lower())}\b", text) for w in words)


def enforce_owners(summary: MeetingSummary, transcript: str) -> MeetingSummary:
    """Safety net: an owner that never appears in the transcript becomes Unassigned."""
    for item in summary.action_items:
        owner = item.owner.strip()
        if not owner or (owner != UNASSIGNED and not _named_in(owner, transcript)):
            item.owner = UNASSIGNED
    return summary


async def run(ctx: AgentContext) -> AsyncIterator[Event]:
    text = _meeting_text(ctx)
    s = get_settings()
    request = f"Request: {ctx.instruction}\n\n"
    if count_tokens(text) <= s.long_input_tokens:
        yield status_event("Summarizing the meeting…")
        summary = await ask(
            "smart", MeetingSummary, SUMMARY_SYSTEM, request + wrap("transcript", text)
        )
    else:
        parts = split_tokens(text, s.map_chunk_tokens)
        partials: list[MeetingSummary] = []
        for i, part in enumerate(parts, start=1):
            yield status_event(f"Reading transcript part {i} of {len(parts)}…")
            user = f"Part {i} of {len(parts)}.\n\n" + wrap("transcript", part)
            partials.append(await ask("fast", MeetingSummary, MAP_SYSTEM, user))
        yield status_event("Merging notes…")
        summary = await ask(
            "smart", MeetingSummary, REDUCE_SYSTEM, request + partials_json(partials)
        )
    summary = enforce_owners(summary, text)
    yield result_event(AgentName.meeting, summary, markdown=summary.to_markdown())
