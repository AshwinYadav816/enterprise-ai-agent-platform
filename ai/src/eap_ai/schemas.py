"""Shared Pydantic models: the contract between the backend and the AI module."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentName(StrEnum):
    research = "research"
    email = "email"
    report = "report"
    meeting = "meeting"
    document = "document"
    chat = "chat"


class DocMeta(BaseModel):
    doc_id: str
    org_id: str
    owner_id: str
    allowed_roles: list[str]


class UserCtx(BaseModel):
    user_id: str
    org_id: str
    roles: list[str]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class AgentRequest(BaseModel):
    query: str
    user: UserCtx
    history: list[ChatMessage] = Field(default_factory=list)
    history_summary: str | None = None
    force_agent: AgentName | None = None
    doc_ids: list[str] | None = None
    transcript: str | None = None


EventType = Literal["status", "agent", "token", "sources", "result", "done", "error"]


class Event(BaseModel):
    type: EventType
    data: dict[str, Any] = Field(default_factory=dict)


class Source(BaseModel):
    n: int
    doc_id: str
    filename: str
    page: int | None = None
    snippet: str


class IngestResult(BaseModel):
    chunks: int
    pages: int
    warnings: list[str] = Field(default_factory=list)
