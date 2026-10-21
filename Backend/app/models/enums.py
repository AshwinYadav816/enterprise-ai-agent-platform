"""Python enums mapped to Postgres ENUM types (values are stored, lowercase)."""

from enum import StrEnum

from sqlalchemy import Enum


class UserRole(StrEnum):
    admin = "admin"
    manager = "manager"
    employee = "employee"


class DocumentStatus(StrEnum):
    processing = "processing"
    ready = "ready"
    failed = "failed"


class MessageRole(StrEnum):
    user = "user"
    assistant = "assistant"


class MessageStatus(StrEnum):
    complete = "complete"
    interrupted = "interrupted"
    error = "error"


class GenerationKind(StrEnum):
    meeting = "meeting"
    report = "report"
    email = "email"
    document_insights = "document_insights"


def pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """Postgres ENUM storing the enum *values* (not member names)."""
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])
