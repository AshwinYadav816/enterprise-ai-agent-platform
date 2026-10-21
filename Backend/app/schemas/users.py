import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import UserRole

PASSWORD_MIN = 8
PASSWORD_MAX = 128  # Argon2 handles long input, but cap it to bound hashing cost


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime


class UpdateMeRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX)
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)
