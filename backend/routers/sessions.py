from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user, require_csrf_protection
from backend.models import ChatMessage, ChatSession, User
from backend.schemas.chat import MessageResponse, SessionResponse
from backend.services.conversations import legacy_session, owned_session


router = APIRouter(prefix="/api/sessions", tags=["conversations"])


@router.get("", response_model=list[SessionResponse])
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    legacy_session(db, user.id)
    return db.scalars(select(ChatSession).where(ChatSession.user_id == user.id)
                      .order_by(ChatSession.updated_at.desc(), ChatSession.id)).all()


@router.post("", response_model=SessionResponse, status_code=201)
def create_session(user: User = Depends(get_current_user),
                   csrf: None = Depends(require_csrf_protection), db: Session = Depends(get_db)):
    session = ChatSession(user_id=user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
def list_messages(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_session(db, user.id, session_id)
    return db.scalars(select(ChatMessage).where(ChatMessage.session_key == session_id)
                      .order_by(ChatMessage.id)).all()
