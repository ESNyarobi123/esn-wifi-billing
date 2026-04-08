from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, EmailStr, Field, PlainValidator


def _login_email(v: object) -> str:
    """Like ``EmailStr`` but allows dev hostnames rejected by strict RFC checks (e.g. ``*.local``)."""
    if not isinstance(v, str):
        raise TypeError("email must be a string")
    s = v.strip()
    if not s:
        raise ValueError("email is required")
    try:
        return validate_email(s, check_deliverability=False).normalized
    except EmailNotValidError:
        if s.count("@") != 1:
            raise ValueError("invalid email address") from None
        local, domain = s.split("@", 1)
        if not local or not domain:
            raise ValueError("invalid email address") from None
        if "." not in domain and domain.lower() != "localhost":
            raise ValueError("invalid email address") from None
        return s.lower()


LoginEmail = Annotated[str, PlainValidator(_login_email)]


class LoginRequest(BaseModel):
    email: LoginEmail
    password: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserPublic(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = ""


class UserUpdate(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None


class MeProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)
