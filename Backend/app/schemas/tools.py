import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import GenerationKind

MAX_TRANSCRIPT_CHARS = 200_000

ReportType = Literal["weekly", "monthly", "sprint", "project"]
EmailTask = Literal["draft", "rewrite", "grammar", "tone", "summarize_thread"]
EmailTone = Literal["formal", "friendly", "concise", "persuasive"]


class MeetingRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=MAX_TRANSCRIPT_CHARS)
    title: str | None = Field(default=None, max_length=200)


class ReportRequest(BaseModel):
    report_type: ReportType
    period: str = Field(min_length=1, max_length=100, examples=["14–20 Oct 2026", "Sprint 7"])
    instruction: str = Field(min_length=1, max_length=4000)
    doc_ids: list[uuid.UUID] | None = Field(default=None, max_length=20)


class EmailRequest(BaseModel):
    task: EmailTask
    tone: EmailTone | None = None
    text: str = Field(min_length=1, max_length=20_000, description="Notes, draft or thread")


class GenerationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: GenerationKind
    title: str
    input: dict[str, Any]
    output: dict[str, Any]
    markdown: str | None
    prompt_tokens: int
    completion_tokens: int
    created_at: datetime


class GenerationSummary(BaseModel):
    """List item: no input/output payloads."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: GenerationKind
    title: str
    created_at: datetime
