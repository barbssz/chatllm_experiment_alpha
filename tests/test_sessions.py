from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock
from sqlalchemy import select

from backend.models import ChatMessage


@pytest.fixture(autouse=True)
def fake_openrouter(monkeypatch):
    """Substitui o provedor externo para que os testes sejam deterministicos."""
    reply = AsyncMock(return_value=("Resposta do modelo", "test-model"))

    async def deltas(**kwargs):
        yield "Resposta "
        yield "do modelo"

    stream = Mock(side_effect=deltas)
    monkeypatch.setattr("backend.routers.chat.generate_reply", reply)
    monkeypatch.setattr("backend.routers.chat.stream_reply", stream)
    return reply, stream


class TestSessionsRequireAuthentication:
    def test_list_requires_session(self, client: TestClient):
        assert client.get("/api/sessions").status_code == 401

    def test_create_requires_session(self, client: TestClient):
        assert client.post("/api/sessions").status_code == 401

    def test_messages_requires_session(self, client: TestClient):
        assert client.get("/api/sessions/qualquer/messages").status_code == 401


class TestSessionCreation:
    def test_create_returns_session_without_title(self, authenticated_client: TestClient):
        response = authenticated_client.post("/api/sessions")
        assert response.status_code == 201
        body = response.json()
        assert body["id"]
        assert body["title"] is None
        assert body["created_at"]
        assert body["updated_at"]

    def test_create_requires_csrf_header(self, authenticated_client: TestClient):
        authenticated_client.headers.pop("X-Requested-With")
        assert authenticated_client.post("/api/sessions").status_code == 403

    def test_created_sessions_appear_in_list(self, authenticated_client: TestClient):
        first = authenticated_client.post("/api/sessions").json()
        second = authenticated_client.post("/api/sessions").json()
        ids = [item["id"] for item in authenticated_client.get("/api/sessions").json()]
        assert first["id"] in ids
        assert second["id"] in ids

    def test_sessions_are_scoped_to_owner(self, authenticated_client: TestClient, credentials):
        mine = authenticated_client.post("/api/sessions").json()
        other = {**credentials, "email": "bob@example.com"}
        authenticated_client.post("/api/auth/register", json=other)
        authenticated_client.post("/api/auth/login", json=other)
        ids = [item["id"] for item in authenticated_client.get("/api/sessions").json()]
        assert mine["id"] not in ids


class TestAutomaticTitle:
    def test_first_reply_sets_title_from_user_message(self, authenticated_client: TestClient):
        session = authenticated_client.post("/api/sessions").json()
        response = authenticated_client.post(
            "/api/chat",
            json={"message": "Como funciona o pipeline mastery aware", "session_id": session["id"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["session_id"] == session["id"]
        assert body["title"] == "Como funciona o pipeline mastery aware"

    def test_title_is_not_overwritten_on_later_turns(self, authenticated_client: TestClient):
        session = authenticated_client.post("/api/sessions").json()
        first = authenticated_client.post(
            "/api/chat", json={"message": "Primeira pergunta", "session_id": session["id"]}
        ).json()
        second = authenticated_client.post(
            "/api/chat", json={"message": "Segunda pergunta", "session_id": session["id"]}
        ).json()
        assert first["title"] == "Primeira pergunta"
        assert second["title"] == "Primeira pergunta"

    def test_long_message_is_truncated_with_ellipsis(self, authenticated_client: TestClient):
        session = authenticated_client.post("/api/sessions").json()
        long_message = "palavra " * 12
        body = authenticated_client.post(
            "/api/chat", json={"message": long_message.strip(), "session_id": session["id"]}
        ).json()
        assert body["title"].endswith("…")
        assert len(body["title"]) <= 78

    def test_stream_done_event_carries_title(self, authenticated_client: TestClient):
        session = authenticated_client.post("/api/sessions").json()
        response = authenticated_client.post(
            "/api/chat/stream", json={"message": "Titulo via stream", "session_id": session["id"]}
        )
        assert response.status_code == 200
        assert '"done": true' in response.text
        assert f'"session_id": "{session["id"]}"' in response.text
        assert '"title": "Titulo via stream"' in response.text


class TestSessionHistory:
    def test_messages_endpoint_returns_stored_turns(self, authenticated_client: TestClient, db_session):
        session = authenticated_client.post("/api/sessions").json()
        authenticated_client.post("/api/chat", json={"message": "Ola", "session_id": session["id"]})

        messages = authenticated_client.get(f"/api/sessions/{session['id']}/messages").json()
        assert [item["role"] for item in messages] == ["user", "assistant"]
        assert messages[0]["content"] == "Ola"
        assert messages[1]["content"] == "Resposta do modelo"

        stored = db_session.scalars(
            select(ChatMessage).where(ChatMessage.session_key == session["id"])
        ).all()
        assert [item.role for item in stored] == ["user", "assistant"]

    def test_history_is_isolated_between_sessions(self, authenticated_client: TestClient):
        first = authenticated_client.post("/api/sessions").json()
        second = authenticated_client.post("/api/sessions").json()
        authenticated_client.post("/api/chat", json={"message": "Conversa A", "session_id": first["id"]})
        authenticated_client.post("/api/chat", json={"message": "Conversa B", "session_id": second["id"]})

        first_messages = authenticated_client.get(f"/api/sessions/{first['id']}/messages").json()
        second_messages = authenticated_client.get(f"/api/sessions/{second['id']}/messages").json()
        assert [item["content"] for item in first_messages] == ["Conversa A", "Resposta do modelo"]
        assert [item["content"] for item in second_messages] == ["Conversa B", "Resposta do modelo"]

    def test_chat_falls_back_when_session_id_is_absent(self, authenticated_client: TestClient):
        """Sem session_id, o turno entra na conversa legada do usuario."""
        body = authenticated_client.post("/api/chat", json={"message": "Historico antigo"}).json()
        assert body["session_id"] == "user:1"
        legacy = next(
            item for item in authenticated_client.get("/api/sessions").json()
            if item["id"] == "user:1"
        )
        assert legacy["title"] == "Historico antigo"


class TestSessionOwnership:
    def test_unknown_session_returns_404(self, authenticated_client: TestClient):
        assert authenticated_client.get("/api/sessions/inexistente/messages").status_code == 404
        response = authenticated_client.post(
            "/api/chat", json={"message": "Ola", "session_id": "inexistente"}
        )
        assert response.status_code == 404

    def test_cannot_read_or_write_another_users_session(
        self, authenticated_client: TestClient, credentials
    ):
        session = authenticated_client.post("/api/sessions").json()
        other = {**credentials, "email": "bob@example.com"}
        authenticated_client.post("/api/auth/register", json=other)
        authenticated_client.post("/api/auth/login", json=other)

        assert authenticated_client.get(f"/api/sessions/{session['id']}/messages").status_code == 404
        blocked = authenticated_client.post(
            "/api/chat", json={"message": "Invasao", "session_id": session["id"]}
        )
        assert blocked.status_code == 404
