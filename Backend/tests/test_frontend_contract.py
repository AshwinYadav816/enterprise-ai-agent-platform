"""Shapes the frontend renders but OpenAPI can't describe (they travel inside SSE `result` events
and `MessageOut.results`): Frontend/src/lib/chat/types.ts + components/chat/result-card.tsx.

If this fails, the AI module changed a result model: update those two frontend files, then the
expected fields here.
"""

from eap_ai.agents.document import DocumentInsights
from eap_ai.agents.email import EmailOutput
from eap_ai.agents.meeting import ActionItem, MeetingSummary
from eap_ai.agents.report import Report, ReportSection
from eap_ai.schemas import Source
from pydantic import BaseModel

FRONTEND_SHAPES: dict[type[BaseModel], set[str]] = {
    MeetingSummary: {"summary", "key_decisions", "action_items", "open_questions"},
    ActionItem: {"task", "owner", "due_date"},
    EmailOutput: {"subject", "body", "notes"},
    Report: {
        "report_type",
        "title",
        "period",
        "sections",
        "highlights",
        "risks",
        "next_steps",
    },
    ReportSection: {"heading", "content_md"},
    DocumentInsights: {"summary", "key_points", "entities", "questions_to_ask"},
    Source: {"n", "doc_id", "filename", "page", "snippet"},
}


def test_ai_result_shapes_match_what_the_frontend_renders() -> None:
    for model, fields in FRONTEND_SHAPES.items():
        assert set(model.model_fields) == fields, model.__name__
