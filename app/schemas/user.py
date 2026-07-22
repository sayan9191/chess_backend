"""User-related Pydantic schemas."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRegisterRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15, examples=["9876543210"])
    name: str = Field(..., min_length=2, max_length=100, examples=["Alice"])

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        cleaned = re.sub(r"[\s\-+]", "", value)
        if not cleaned.isdigit():
            raise ValueError("Phone number must contain digits only")
        return cleaned


class UserLoginRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15, examples=["9876543210"])

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        cleaned = re.sub(r"[\s\-+]", "", value)
        if not cleaned.isdigit():
            raise ValueError("Phone number must contain digits only")
        return cleaned


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone: str
    name: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
