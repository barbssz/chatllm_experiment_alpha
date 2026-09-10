from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import config
from backend.database import Base, get_db
from backend.main import app
from backend.models import AuthSession, User, utc_now
from backend.services.auth import hash_session_token, password_hasher


def test_register_normalizes_email_and_hashes_password(client, db_session, credentials):
    response = client.post("/api/auth/register", json={**credentials, "email": "  ALICE@Example.com  "})
    assert response.status_code == 201
    assert response.json() == {"id": 1, "email": "alice@example.com"}
    user = db_session.scalar(select(User))
    assert user.password_hash.startswith("$argon2id$")
    assert password_hasher.verify(credentials["password"], user.password_hash)
    assert user.created_at <= utc_now()
    assert credentials["password"] not in response.text
    assert client.get("/api/auth/me").status_code == 401


def test_duplicate_email_rejected_case_insensitively(client, db_session, credentials):
    assert client.post("/api/auth/register", json=credentials).status_code == 201
    response = client.post("/api/auth/register", json={**credentials, "email": credentials["email"].upper()})
    assert response.status_code == 409
    assert db_session.scalar(select(func.count()).select_from(User)) == 1


def test_concurrent_duplicate_conflict_rolls_back(client, db_session, credentials, monkeypatch):
    def conflicting_commit():
        raise IntegrityError("INSERT users", {}, Exception("UNIQUE constraint failed"))

    with monkeypatch.context() as patch:
        patch.setattr(db_session, "commit", conflicting_commit)
        assert client.post("/api/auth/register", json=credentials).status_code == 409
    # O rollback deixa a mesma sessao utilizavel para uma operacao seguinte.
    assert client.post("/api/auth/register", json=credentials).status_code == 201


@pytest.mark.parametrize("changes", [
    {"email": "invalido"}, {"email": ""}, {"password": "curta"},
    {"password": "x" * 129}, {"password": ""}, {"password": 12345},
])
def test_invalid_registration_is_rejected_without_echoing_password(client, credentials, changes):
    payload = {**credentials, **changes}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422
    assert all("input" not in error for error in response.json()["detail"])


def test_password_whitespace_is_preserved(client, credentials):
    credentials["password"] = "  uma frase longa  "
    assert client.post("/api/auth/register", json=credentials).status_code == 201
    assert client.post("/api/auth/login", json={**credentials, "password": credentials["password"].strip()}).status_code == 401
    assert client.post("/api/auth/login", json=credentials).status_code == 200


def test_login_sets_cookie_and_me_returns_only_public_user(authenticated_client, db_session, credentials):
    response = authenticated_client.post("/api/auth/login", json=credentials)
    cookie_header = response.headers["set-cookie"]
    assert "HttpOnly" in cookie_header
    assert "SameSite=lax" in cookie_header
    assert "Path=/" in cookie_header
    assert f"Max-Age={config.AUTH_SESSION_SECONDS}" in cookie_header
    token = authenticated_client.cookies.get(config.AUTH_COOKIE_NAME)
    session = db_session.scalar(select(AuthSession))
    assert session.token_hash == hash_session_token(token)
    assert session.token_hash != token
    assert utc_now() < session.expires_at <= utc_now() + timedelta(seconds=config.AUTH_SESSION_SECONDS)
    me = authenticated_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == response.json()
    assert set(me.json()) == {"id", "email"}
    assert "no-store" in me.headers["cache-control"]


def test_secure_cookie_configuration(client, credentials, monkeypatch):
    client.post("/api/auth/register", json=credentials)
    monkeypatch.setattr(config, "AUTH_COOKIE_SECURE", True)
    response = client.post("/api/auth/login", json=credentials)
    assert "Secure" in response.headers["set-cookie"]


def test_invalid_credentials_have_same_error(client, credentials):
    client.post("/api/auth/register", json=credentials)
    wrong_password = client.post("/api/auth/login", json={**credentials, "password": "senha incorreta"})
    unknown_user = client.post("/api/auth/login", json={**credentials, "email": "unknown@example.com"})
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()
    assert config.AUTH_COOKIE_NAME not in client.cookies


@pytest.mark.parametrize("token", [None, "forjado", "x" * 129])
def test_me_rejects_missing_or_invalid_session(client, token):
    if token:
        client.cookies.set(config.AUTH_COOKIE_NAME, token)
    assert client.get("/api/auth/me").status_code == 401


def test_expired_session_rejected_and_cleaned_on_login(authenticated_client, db_session, credentials):
    session = db_session.scalar(select(AuthSession))
    session.expires_at = utc_now() - timedelta(seconds=1)
    db_session.commit()
    assert authenticated_client.get("/api/auth/me").status_code == 401
    for endpoint in ("/api/chat", "/api/chat/stream"):
        assert authenticated_client.post(endpoint, json={"message": "Ola"}).status_code == 401
    assert authenticated_client.post("/api/auth/login", json=credentials).status_code == 200
    assert db_session.scalar(select(func.count()).select_from(AuthSession)) == 1


def test_logout_revokes_session_even_when_cookie_is_replayed(authenticated_client, db_session):
    old_token = authenticated_client.cookies.get(config.AUTH_COOKIE_NAME)
    response = authenticated_client.post("/api/auth/logout")
    assert response.status_code == 204
    assert response.content == b""
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert config.AUTH_COOKIE_NAME not in authenticated_client.cookies
    assert db_session.scalar(select(func.count()).select_from(AuthSession)) == 0
    authenticated_client.cookies.set(config.AUTH_COOKIE_NAME, old_token)
    assert authenticated_client.get("/api/auth/me").status_code == 401
    for endpoint in ("/api/chat", "/api/chat/stream"):
        assert authenticated_client.post(endpoint, json={"message": "Ola"}).status_code == 401


def test_logout_is_idempotent(client):
    assert client.post("/api/auth/logout").status_code == 204
    assert client.post("/api/auth/logout").status_code == 204


def test_login_rotates_current_session(authenticated_client, db_session, credentials):
    old_token = authenticated_client.cookies.get(config.AUTH_COOKIE_NAME)
    authenticated_client.post("/api/auth/login", json=credentials)
    new_token = authenticated_client.cookies.get(config.AUTH_COOKIE_NAME)
    assert new_token != old_token
    assert db_session.scalar(select(func.count()).select_from(AuthSession)) == 1
    authenticated_client.cookies.clear()
    authenticated_client.cookies.set(config.AUTH_COOKIE_NAME, old_token)
    assert authenticated_client.get("/api/auth/me").status_code == 401


def test_logout_does_not_revoke_another_browser(authenticated_client, credentials):
    first_token = authenticated_client.cookies.get(config.AUTH_COOKIE_NAME)
    authenticated_client.cookies.clear()
    authenticated_client.post("/api/auth/login", json=credentials)
    second_token = authenticated_client.cookies.get(config.AUTH_COOKIE_NAME)
    assert first_token != second_token
    authenticated_client.post("/api/auth/logout")
    authenticated_client.cookies.set(config.AUTH_COOKIE_NAME, first_token)
    assert authenticated_client.get("/api/auth/me").status_code == 200


@pytest.mark.parametrize("endpoint", ["register", "login", "logout"])
@pytest.mark.parametrize("attack", ["missing_header", "wrong_header", "foreign_origin", "null_origin"])
def test_auth_mutations_require_csrf_protection(client, credentials, endpoint, attack):
    if attack == "missing_header":
        client.headers.pop("X-Requested-With")
    elif attack == "wrong_header":
        client.headers["X-Requested-With"] = "wrong"
    else:
        client.headers["Origin"] = "null" if attack == "null_origin" else "https://evil.example"
    assert client.post(f"/api/auth/{endpoint}", json=credentials).status_code == 403


def test_api_client_without_origin_still_requires_custom_header(client, credentials):
    client.headers.pop("Origin")
    assert client.post("/api/auth/register", json=credentials).status_code == 201
    client.headers.pop("X-Requested-With")
    assert client.post("/api/auth/login", json=credentials).status_code == 403


def test_users_and_sessions_survive_database_reopen(tmp_path, monkeypatch, credentials):
    database_url = f"sqlite:///{tmp_path / 'persistent.db'}"
    token = None
    for restart in range(2):
        persistent_engine = create_engine(database_url, connect_args={"check_same_thread": False})
        monkeypatch.setattr("backend.main.engine", persistent_engine)

        def persistent_db():
            with Session(persistent_engine) as db:
                yield db

        app.dependency_overrides[get_db] = persistent_db
        try:
            with TestClient(app, base_url="http://localhost:8000", headers={"X-Requested-With": "ChatLLM"}) as client:
                if restart == 0:
                    assert client.post("/api/auth/register", json=credentials).status_code == 201
                    assert client.post("/api/auth/login", json=credentials).status_code == 200
                    token = client.cookies.get(config.AUTH_COOKIE_NAME)
                else:
                    client.cookies.set(config.AUTH_COOKIE_NAME, token)
                    assert client.get("/api/auth/me").json()["email"] == credentials["email"]
                    assert client.post("/api/auth/login", json=credentials).status_code == 200
        finally:
            app.dependency_overrides.clear()
            persistent_engine.dispose()
