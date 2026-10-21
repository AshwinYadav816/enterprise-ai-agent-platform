from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.users import PASSWORD_MAX, PASSWORD_MIN, UserOut


def _lower(value: str) -> str:
    return value.strip().lower()


class RegisterRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=200)
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)

    _normalize_email = field_validator("email")(_lower)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX)

    _normalize_email = field_validator("email")(_lower)


class TokenResponse(BaseModel):
    """Access token in the body (keep it in memory); refresh token is set as an httpOnly cookie."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # seconds
    must_change_password: bool
    user: UserOut
