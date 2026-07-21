"""Request/response models."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class TokenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr


class TokenResponse(BaseModel):
    token: str
    type: str
    name: str
    email: str
    expires_at: str | None


class ValidateRequest(BaseModel):
    token: str


class ValidateResponse(BaseModel):
    valid: bool
    reason: str = ""
    type: str | None = None
    name: str | None = None
    email: str | None = None
    expires_at: str | None = None
