from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend import config
from backend.database import get_db
from backend.models import User
from backend.services.auth import user_for_session


def require_csrf_protection(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    # Cabecalho nao simples: outros sites precisam de preflight, restrito pelo CORS.
    # Tambem protege login/cadastro, sem precisar de uma sessao pre-autenticada.
    origin = request.headers.get("origin")
    if request.headers.get("x-requested-with") != "ChatLLM" or (
        origin is not None and origin not in config.ALLOWED_ORIGINS
    ):
        raise HTTPException(status_code=403, detail="Origem ou cabecalho de seguranca invalido.")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = user_for_session(db, request.cookies.get(config.AUTH_COOKIE_NAME))
    if user is None:
        raise HTTPException(status_code=401, detail="Sessao ausente ou expirada. Entre novamente.")
    return user
