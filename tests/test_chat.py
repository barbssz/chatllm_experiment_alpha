from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock
from sqlalchemy import select

from backend import config
from backend.models import ChatMessage
from backend.services.openrouter import OpenRouterConfigError


@pytest.fixture(autouse=True)
def fake_openrouter(monkeypatch):
    reply = AsyncMock(return_value=("Ola de volta", "test-model"))

    async def deltas(**kwargs):
        yield "Ola "
        yield "de volta"

    stream = Mock(side_effect=deltas)
    monkeypatch.setattr("backend.routers.chat.generate_reply", reply)
    monkeypatch.setattr("backend.routers.chat.stream_reply", stream)
    return reply, stream


class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestRootEndpoint:
    def test_root_returns_frontend(self, client: TestClient):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


@pytest.mark.parametrize("endpoint", ["/api/chat", "/api/chat/stream"])
class TestChatRequiresAuthentication:
    def test_chat_rejected_without_session(self, endpoint, client: TestClient):
        """Sem cookie de sessao, o chat deve responder 401 (rota protegida)."""
        response = client.post(endpoint, json={"message": "Ola"})
        assert response.status_code == 401

    @pytest.mark.parametrize("token", ["forjado", "x" * 129])
    def test_chat_rejected_with_invalid_session(self, endpoint, token, client: TestClient):
        """Cookie invalido nao autentica: continua 401."""
        client.cookies.set(config.AUTH_COOKIE_NAME, token)
        assert client.post(endpoint, json={"message": "Ola"}).status_code == 401


class TestChatEndpoint:
    def test_chat_returns_reply_and_session_metadata(self, authenticated_client: TestClient):
        """A resposta inclui o texto do modelo e os metadados da conversa."""
        response = authenticated_client.post("/api/chat", json={"message": "Ola"})
        assert response.status_code == 200
        body = response.json()
        assert body["reply"] == "Ola de volta"
        assert body["model"] == "test-model"
        assert body["session_id"] == "user:1"
        assert body["title"] == "Ola"

    def test_chat_empty_message_rejected(self, authenticated_client: TestClient):
        """Autenticado, mensagem vazia deve ser rejeitada com 422 (Pydantic)."""
        response = authenticated_client.post("/api/chat", json={"message": ""})
        assert response.status_code == 422

    def test_chat_persists_messages_under_user_session_key(
        self, authenticated_client: TestClient, db_session, monkeypatch
    ):
        """As mensagens ficam associadas ao usuario autenticado."""

        async def fake_generate_reply(*, user_message, history, model=None):
            return "resposta de teste", "google/gemma-4-31b-it"

        monkeypatch.setattr("backend.routers.chat.generate_reply", fake_generate_reply)

        response = authenticated_client.post("/api/chat", json={"message": "Ola"})
        assert response.status_code == 200

        rows = db_session.query(ChatMessage).order_by(ChatMessage.id).all()
        assert [row.role for row in rows] == ["user", "assistant"]
        assert {row.session_key for row in rows} == {"user:1"}
        assert rows[0].content == "Ola"
        assert rows[1].content == "resposta de teste"


class TestChatStreamEndpoint:
    def test_chat_stream_reaches_model_layer_when_authenticated(self, authenticated_client: TestClient, db_session):
        """O stream autenticado entrega deltas e persiste as mensagens."""
        response = authenticated_client.post("/api/chat/stream", json={"message": "Ola"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert '"delta": "Ola "' in response.text
        assert '"done": true' in response.text
        assert '"session_id": "user:1"' in response.text
        messages = db_session.scalars(select(ChatMessage).order_by(ChatMessage.id)).all()
        assert [item.content for item in messages] == ["Ola", "Ola de volta"]
        assert {item.session_key for item in messages} == {"user:1"}

    def test_chat_stream_empty_message_rejected(self, authenticated_client: TestClient):
        """Stream autenticado com mensagem vazia deve ser rejeitado com 422."""
        response = authenticated_client.post("/api/chat/stream", json={"message": ""})
        assert response.status_code == 422


class TestCORSMiddleware:
    def test_cors_allows_configured_origin(self, client: TestClient):
        """A origem configurada em ALLOWED_ORIGINS deve ser aceita no preflight."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:8000"

    def test_cors_rejects_unknown_origin(self, client: TestClient):
        """Origem fora da allowlist nao deve receber cabecalhos CORS."""
        response = client.options(
            "/health",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("endpoint", ["/api/chat", "/api/chat/stream"])
def test_anonymous_chat_never_calls_openrouter(client, fake_openrouter, endpoint):
    assert client.post(endpoint, json={"message": "Ola"}).status_code == 401
    for mocked in fake_openrouter:
        mocked.assert_not_called()


@pytest.mark.parametrize("endpoint", ["/api/chat", "/api/chat/stream"])
@pytest.mark.parametrize("attack", ["missing_header", "foreign_origin"])
def test_chat_requires_csrf_protection(authenticated_client, fake_openrouter, endpoint, attack):
    if attack == "missing_header":
        authenticated_client.headers.pop("X-Requested-With")
    else:
        authenticated_client.headers["Origin"] = "https://evil.example"
    assert authenticated_client.post(endpoint, json={"message": "Ola"}).status_code == 403
    for mocked in fake_openrouter:
        mocked.assert_not_called()


@pytest.mark.parametrize("error", [OpenRouterConfigError("Sem chave"), RuntimeError("Falha no provedor")])
def test_authenticated_chat_preserves_provider_errors(authenticated_client, fake_openrouter, db_session, error):
    reply, stream = fake_openrouter
    reply.side_effect = error

    async def failed_stream(**kwargs):
        raise error
        yield  # pragma: no cover

    stream.side_effect = failed_stream
    response = authenticated_client.post("/api/chat", json={"message": "Ola"})
    assert response.status_code == (503 if isinstance(error, OpenRouterConfigError) else 502)
    response = authenticated_client.post("/api/chat/stream", json={"message": "Ola"})
    assert response.status_code == 200
    assert '"error":' in response.text
    assert db_session.scalars(select(ChatMessage)).all() == []


def test_messages_are_scoped_to_authenticated_user(authenticated_client, db_session, credentials):
    authenticated_client.post("/api/chat", json={"message": "Primeira conta"})
    other = {**credentials, "email": "bob@example.com"}
    authenticated_client.post("/api/auth/register", json=other)
    authenticated_client.post("/api/auth/login", json=other)
    authenticated_client.post("/api/chat/stream", json={"message": "Segunda conta"})
    messages = db_session.scalars(select(ChatMessage).where(ChatMessage.role == "user")).all()
    assert {(item.content, item.session_key) for item in messages} == {
        ("Primeira conta", "user:1"), ("Segunda conta", "user:2"),
    }
