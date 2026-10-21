import uuid
from datetime import datetime
from typing import Any

from eap_ai.schemas import AgentName
from pydantic import BaseModel, ConfigDict, Field

from app.models import MessageRole, MessageStatus


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class UpdateConversationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: MessageRole
    content: str
    agent: str | None
    sources: list[Any] | None
    results: list[Any] | None
    status: MessageStatus
    prompt_tokens: int
    completion_tokens: int
    created_at: datetime


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    doc_ids: list[uuid.UUID] | None = Field(
        default=None, max_length=20, description="Restrict answers to these documents"
    )
    force_agent: AgentName | None = Field(
        default=None, description="Skip the router (research|email|meeting|report|document|chat)"
    )
