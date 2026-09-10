from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import config
from backend.database import get_db
from backend.dependencies import get_current_user, require_csrf_protection
from backend.models import User
from backend.schemas.auth import LoginRequest, RegisterRequest, UserResponse
from backend.services.auth import authenticate_user, create_session, hash_password, revoke_session


router = APIRouter(
    prefix="/api/auth", tags=["auth"], dependencies=[Depends(require_csrf_protection)]
)


@router.post("/register", response_model=UserResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    if db.scalar(select(User.id).where(User.email == payload.email)) is not None:
        raise HTTPException(status_code=409, detail="Este e-mail ja esta cadastrado.")
    user = User(email=payload.email, password_hash=hash_password(payload.password.get_secret_value()))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Este e-mail ja esta cadastrado.") from exc
    db.refresh(user)
    return user


@router.post("/login", response_model=UserResponse)
def login(
    payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> User:
    user = authenticate_user(db, payload.email, payload.password.get_secret_value())
    if user is None:
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    token = create_session(db, user, request.cookies.get(config.AUTH_COOKIE_NAME))
    response.set_cookie(
        key=config.AUTH_COOKIE_NAME, value=token, max_age=config.AUTH_SESSION_SECONDS,
        httponly=True, secure=config.AUTH_COOKIE_SECURE, samesite="lax", path="/",
    )
    return user


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    revoke_session(db, request.cookies.get(config.AUTH_COOKIE_NAME))
    db.commit()
    response = Response(status_code=204)
    response.delete_cookie(
        key=config.AUTH_COOKIE_NAME, path="/", httponly=True,
        secure=config.AUTH_COOKIE_SECURE, samesite="lax",
    )
    return response
