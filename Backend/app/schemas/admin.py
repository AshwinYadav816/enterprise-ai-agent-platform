import uuid
from datetime import date, datetime
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


# --- dashboard stats (GET /admin/stats) ---------------------------------------------------


class UserStats(BaseModel):
    total: int
    by_role: dict[str, int]  # every role present, 0 if none
    active_last_7_days: int  # logged in within the last 7 days
    deactivated: int


class DocumentStats(BaseModel):
    total: int
    by_status: dict[str, int]
    storage_bytes: int


class CountStats(BaseModel):
    total: int


class GenerationStats(BaseModel):
    total: int
    by_kind: dict[str, int]


class TokensPerDay(BaseModel):
    date: date
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class AgentUsage(BaseModel):
    agent: str
    requests: int
    tokens: int


class TokenStats(BaseModel):
    last_30_days_total: int
    per_day: list[TokensPerDay]  # 30 entries, oldest first, missing days = 0
    per_agent: list[AgentUsage]  # last 30 days, most tokens first


class AdminStats(BaseModel):
    generated_at: datetime
    users: UserStats
    documents: DocumentStats
    conversations: CountStats
    messages: CountStats
    generations: GenerationStats
    tokens: TokenStats
