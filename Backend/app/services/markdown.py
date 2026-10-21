"""Pure Markdown renderers for tool outputs (used for display and PDF export).

Meeting and report results from the AI module already carry `markdown`; these renderers cover
email and document insights, and act as a fallback for the other two.
"""

from collections.abc import Callable
from typing import Any

from app.models import GenerationKind


def _cell(value: Any) -> str:
    return str(value or "—").replace("|", "\\|").replace("\n", " ").strip() or "—"


def _bullets(heading: str, items: list[Any] | None) -> list[str]:
    return ["", f"## {heading}", *[f"- {i}" for i in items]] if items else []


def render_meeting(out: dict[str, Any], title: str = "Meeting summary") -> str:
    lines = [f"# {title}", "", str(out.get("summary", "")).strip()]
    lines += _bullets("Key decisions", out.get("key_decisions"))
    if items := out.get("action_items"):
        lines += ["", "## Action items", "", "| Task | Owner | Due |", "|---|---|---|"]
        lines += [
            f"| {_cell(a.get('task'))} | {_cell(a.get('owner') or 'Unassigned')} "
            f"| {_cell(a.get('due_date'))} |"
            for a in items
        ]
    lines += _bullets("Open questions", out.get("open_questions"))
    return "\n".join(lines) + "\n"


def render_report(out: dict[str, Any], title: str = "Report") -> str:
    kind = str(out.get("report_type", "")).title()
    lines = [f"# {out.get('title') or title}", "", f"*{kind} report — {out.get('period', '')}*"]
    lines += _bullets("Highlights", out.get("highlights"))
    for section in out.get("sections") or []:
        lines += ["", f"## {section.get('heading', '')}", "", str(section.get("content_md", ""))]
    lines += _bullets("Risks", out.get("risks"))
    lines += _bullets("Next steps", out.get("next_steps"))
    return "\n".join(lines) + "\n"


def render_email(out: dict[str, Any], title: str = "Email") -> str:
    lines = [f"# {out.get('subject') or title}", "", str(out.get("body", "")).strip()]
    if notes := str(out.get("notes") or "").strip():
        lines += ["", "---", "", f"*Notes: {notes}*"]
    return "\n".join(lines) + "\n"


def render_insights(out: dict[str, Any], title: str = "Document insights") -> str:
    lines = [f"# {title}", "", str(out.get("summary", "")).strip()]
    lines += _bullets("Key points", out.get("key_points"))
    lines += _bullets("Entities", out.get("entities"))
    lines += _bullets("Questions to ask", out.get("questions_to_ask"))
    return "\n".join(lines) + "\n"


_RENDERERS: dict[GenerationKind, Callable[[dict[str, Any], str], str]] = {
    GenerationKind.meeting: render_meeting,
    GenerationKind.report: render_report,
    GenerationKind.email: render_email,
    GenerationKind.document_insights: render_insights,
}


DEFAULT_TITLES = {
    GenerationKind.meeting: "Meeting summary",
    GenerationKind.report: "Report",
    GenerationKind.email: "Email",
    GenerationKind.document_insights: "Document insights",
}


def render(kind: GenerationKind, output: dict[str, Any], title: str | None = None) -> str:
    return _RENDERERS[kind](output, title or DEFAULT_TITLES[kind])
