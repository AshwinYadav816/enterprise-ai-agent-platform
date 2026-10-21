"""Import every model so Base.metadata is complete (Alembic autogenerate relies on this)."""

from app.models.audit import AuditLog
from app.models.base import Base
from app.models.chat import Conversation, Message
from app.models.document import Document
from app.models.enums import (
    DocumentStatus,
    GenerationKind,
    MessageRole,
    MessageStatus,
    UserRole,
)
from app.models.generation import Generation
from app.models.organization import Organization
from app.models.user import RefreshToken, User

__all__ = [
    "AuditLog",
    "Base",
    "Conversation",
    "Document",
    "DocumentStatus",
    "Generation",
    "GenerationKind",
    "Message",
    "MessageRole",
    "MessageStatus",
    "Organization",
    "RefreshToken",
    "User",
    "UserRole",
]
