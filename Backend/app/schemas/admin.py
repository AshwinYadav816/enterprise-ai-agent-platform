import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import UserRole
from app.schemas.users import UserOut


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    role: UserRole = UserRole.employee

    @field_validator("email")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.strip().lower()


class CreatedUserResponse(BaseModel):
    user: UserOut
    temporary_password: str = Field(
        description="Shown ONCE. The user must change it at first login."
    )


class UpdateUserRequest(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> "UpdateUserRequest":
        if self.role is None and self.is_active is None:
            raise ValueError("Provide role and/or is_active")
        return self


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    user_id: uuid.UUID | None
    user_email: str | None = None  # actor, joined for display
    target_type: str | None
    target_id: uuid.UUID | None
    meta: dict[str, Any] | None
    ip: str | None
    created_at: datetime
