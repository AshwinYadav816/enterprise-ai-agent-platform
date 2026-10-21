import uuid
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB  # postgres ARRAY: has .overlap() (&&)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin, UpdatedAtMixin
from app.models.enums import DocumentStatus, pg_enum


class Document(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_org_id_created_at", "org_id", text("created_at DESC")),
        Index("ix_documents_allowed_roles", "allowed_roles", postgresql_using="gin"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        pg_enum(DocumentStatus, "document_status"),
        server_default=DocumentStatus.processing.value,
        nullable=False,
    )
    chunk_count: Mapped[int | None] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer)
    warnings: Mapped[list[Any]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False
    )
    error: Mapped[str | None] = mapped_column(Text)
