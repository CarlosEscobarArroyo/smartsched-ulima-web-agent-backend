"""Schemas del módulo de soporte."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class ContactRequest(BaseModel):
    email: EmailStr
    message: str = Field(min_length=10, max_length=1000)


class ContactMessageOut(BaseModel):
    id: str
    email: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}
