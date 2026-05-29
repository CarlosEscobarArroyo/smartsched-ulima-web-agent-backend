from datetime import datetime

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    mode: str | None = Field(default=None, max_length=60)


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: datetime


class ConversationSummary(BaseModel):
    id: str
    title: str
    mode: str | None = None
    last_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageOut] = []


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
