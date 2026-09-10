import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import ChatMessage, ChatSession, utc_now


def title_from_message(message: str) -> str:
    """Titulo contextual local: primeira pergunta, ate 8 palavras e 80 caracteres."""
    words = re.sub(r"\s+", " ", message).strip().split(" ")
    title = " ".join(words[:8])[:77].rstrip()
    return title + ("…" if len(words) > 8 or len(" ".join(words[:8])) > 77 else "")


def owned_session(db: Session, user_id: int, session_id: str) -> ChatSession:
    session = db.scalar(select(ChatSession).where(
        ChatSession.id == session_id, ChatSession.user_id == user_id,
    ))
    if session is None:
        raise HTTPException(status_code=404, detail="Conversa nao encontrada.")
    return session


def legacy_session(db: Session, user_id: int, *, create: bool = False) -> ChatSession | None:
    """Importa mensagens da tarefa 1 sem alterar seu conteudo ou atribuir mensagens anonimas."""
    key = f"user:{user_id}"
    session = db.get(ChatSession, key)
    if session is not None:
        return owned_session(db, user_id, key)
    first = db.scalar(select(ChatMessage).where(ChatMessage.session_key == key).order_by(ChatMessage.id))
    if first is None and not create:
        return None
    session = ChatSession(id=key, user_id=user_id, title=title_from_message(first.content) if first else None)
    db.add(session)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return owned_session(db, user_id, key)
    db.refresh(session)
    return session


def conversation_history(db: Session, session_id: str) -> list[dict]:
    # O historico completo permanece no banco; limita o contexto enviado ao provedor.
    rows = db.scalars(select(ChatMessage).where(ChatMessage.session_key == session_id)
                      .order_by(ChatMessage.id.desc()).limit(40)).all()
    return [{"role": row.role, "content": row.content} for row in reversed(rows)]


def save_turn(db: Session, session_id: str, message: str, reply: str, model: str) -> str:
    session = db.get(ChatSession, session_id)
    if session is None:
        raise RuntimeError("Conversa indisponivel ao salvar a resposta.")
    db.add_all([
        ChatMessage(session_key=session_id, role="user", content=message, model=model),
        ChatMessage(session_key=session_id, role="assistant", content=reply, model=model),
    ])
    if not session.title:
        session.title = title_from_message(message)
    session.updated_at = utc_now()
    db.commit()
    return session.title
