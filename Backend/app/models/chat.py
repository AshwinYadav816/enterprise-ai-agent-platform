import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin, UpdatedAtMixin
from app.models.enums import MessageRole, MessageStatus, pg_enum


class Conversation(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_id_updated_at", "user_id", text("updated_at DESC")),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)  # rolling summary of older messages
    summarized_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)


class Message(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(pg_enum(MessageRole, "message_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list[Any] | None] = mapped_column(JSONB)
    results: Mapped[list[Any] | None] = mapped_column(JSONB)
    status: Mapped[MessageStatus] = mapped_column(
        pg_enum(MessageStatus, "message_status"),
        server_default=MessageStatus.complete.value,
        nullable=False,
    )
    prompt_tokens: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
