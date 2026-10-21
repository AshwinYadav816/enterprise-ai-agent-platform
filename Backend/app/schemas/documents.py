import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field

from app.models import DocumentStatus, UserRole


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    allowed_roles: list[str]
    status: DocumentStatus
    chunk_count: int | None
    page_count: int | None
    warnings: list[Any]
    error: str | None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def visibility(self) -> UserRole:
        """Lowest role that can see the document (what the uploader picked)."""
        return UserRole(self.allowed_roles[0])
