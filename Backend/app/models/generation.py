import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin
from app.models.enums import GenerationKind, pg_enum


class Generation(IdMixin, CreatedAtMixin, Base):
    """Output of a tool (meeting summary, report, email, document insights)."""

    __tablename__ = "generations"
    __table_args__ = (
        Index("ix_generations_org_id_kind_created_at", "org_id", "kind", text("created_at DESC")),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    kind: Mapped[GenerationKind] = mapped_column(
        pg_enum(GenerationKind, "generation_kind"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    markdown: Mapped[str | None] = mapped_column(Text)
    prompt_tokens: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
