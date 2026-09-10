from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend import config
from backend.models import AuthSession, User, utc_now


password_hasher = PasswordHash.recommended()
# Mantem a verificacao de hash mesmo quando o e-mail nao existe.
_DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    valid = password_hasher.verify(password, user.password_hash if user else _DUMMY_HASH)
    return user if user is not None and valid else None


def hash_session_token(token: str) -> str:
    # SHA-256 se aplica ao token aleatorio de alta entropia, nunca a senha.
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def revoke_session(db: Session, token: str | None) -> None:
    if token:
        db.execute(
            delete(AuthSession).where(AuthSession.token_hash == hash_session_token(token)),
            execution_options={"synchronize_session": "fetch"},
        )


def create_session(db: Session, user: User, previous_token: str | None = None) -> str:
    now = utc_now()
    db.execute(
        delete(AuthSession).where(AuthSession.expires_at <= now),
        execution_options={"synchronize_session": "fetch"},
    )
    revoke_session(db, previous_token)
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=now + timedelta(seconds=config.AUTH_SESSION_SECONDS),
    ))
    db.commit()
    return token


def user_for_session(db: Session, token: str | None) -> User | None:
    if not token or len(token) > 128:
        return None
    return db.scalar(
        select(User).join(AuthSession, AuthSession.user_id == User.id).where(
            AuthSession.token_hash == hash_session_token(token),
            AuthSession.expires_at > utc_now(),
        )
    )
