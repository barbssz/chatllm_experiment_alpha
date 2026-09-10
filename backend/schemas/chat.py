from __future__ import annotations

from typing import Literal
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    model: str | None = None
    history: list[ChatMessageIn] = Field(default_factory=list)
    session_id: str | None = Field(default=None, min_length=1, max_length=120)


class ChatResponse(BaseModel):
    reply: str
    model: str
    session_id: str | None = None
    title: str | None = None


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    content: str
    model: str
    created_at: datetime
