"""Pydantic schemas for authentication endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    pref_lang: str = "zh_hk"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    membership_tier: str
    pref_lang: str
    created_at: datetime

    model_config = {"from_attributes": True}
