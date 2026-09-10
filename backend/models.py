from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base
from backend.config import OPENROUTER_MODEL_DEFAULT


def utc_now() -> datetime:
    # SQLite armazena timestamps sem timezone; usamos UTC em todas as comparacoes.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_key: Mapped[str] = mapped_column(String(120), default="default", index=True)
    role: Mapped[str] = mapped_column(String(20), index=True)
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(120), default=OPENROUTER_MODEL_DEFAULT)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)
