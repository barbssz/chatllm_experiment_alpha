from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.config import OPENROUTER_MODEL_DEFAULT
from backend.database import get_db
from backend.dependencies import get_current_user, require_csrf_protection
from backend.models import ChatMessage, User
from backend.schemas.chat import ChatRequest, ChatResponse
from backend.services.openrouter import OpenRouterConfigError, generate_reply, stream_reply
from backend.services.conversations import owned_session, legacy_session, conversation_history, save_turn


router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    csrf: None = Depends(require_csrf_protection),
    db: Session = Depends(get_db),
) -> ChatResponse:
    conversation = owned_session(db, user.id, payload.session_id) if payload.session_id else legacy_session(db, user.id, create=True)
    session_key = conversation.id
    history = conversation_history(db, session_key)
    try:
        reply, model_name = await generate_reply(
            user_message=payload.message,
            history=history,
            model=payload.model,
        )
    except OpenRouterConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    resolved_model = payload.model or model_name or OPENROUTER_MODEL_DEFAULT

    title = save_turn(db, session_key, payload.message, reply, resolved_model)
    return ChatResponse(reply=reply, model=resolved_model, session_id=session_key, title=title)


@router.post("/api/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    csrf: None = Depends(require_csrf_protection),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    conversation = owned_session(db, user.id, payload.session_id) if payload.session_id else legacy_session(db, user.id, create=True)
    session_key = conversation.id
    history = conversation_history(db, session_key)
    resolved_model = payload.model or OPENROUTER_MODEL_DEFAULT

    async def event_generator():
        full_reply = ""
        try:
            async for delta in stream_reply(
                user_message=payload.message,
                history=history,
                model=payload.model,
            ):
                full_reply += delta
                yield f"data: {json.dumps({'delta': delta}, ensure_ascii=True)}\n\n"
        except OpenRouterConfigError as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=True)}\n\n"
            return
        except RuntimeError as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=True)}\n\n"
            return
        finally:
            # Persiste inclusive o trecho recebido se o navegador cancelar/trocar de conversa.
            if full_reply.strip():
                # A versao de FastAPI usada encerra a dependencia antes do streaming.
                with Session(bind=db.get_bind()) as write_db:
                    title = save_turn(write_db, session_key, payload.message, full_reply, resolved_model)

        if not full_reply.strip():
            yield f"data: {json.dumps({'error': 'O modelo nao retornou uma resposta.'})}\n\n"
            return
        yield f"data: {json.dumps({'done': True, 'session_id': session_key, 'title': title}, ensure_ascii=True)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
