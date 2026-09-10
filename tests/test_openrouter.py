from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.openrouter import (
    OpenRouterConfigError,
    _build_messages,
    _build_headers,
    generate_reply,
    stream_reply,
)


class TestBuildMessages:
    def test_build_messages_minimal(self):
        """Deve construir lista de mensagens com system prompt, usuario e historico vazio."""
        messages = _build_messages(user_message="Ola", history=[])
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "LaTeX" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Ola"

    def test_build_messages_with_history(self):
        """Deve incluir historico entre system prompt e mensagem do usuario."""
        history = [
            {"role": "user", "content": "Pergunta anterior"},
            {"role": "assistant", "content": "Resposta anterior"},
        ]
        messages = _build_messages(user_message="Nova pergunta", history=history)
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Pergunta anterior"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "Resposta anterior"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "Nova pergunta"

    def test_build_messages_filters_invalid_roles(self):
        """Deve filtrar entradas de historico com roles invalidas."""
        history = [
            {"role": "system", "content": "Nao deve aparecer"},
            {"role": "user", "content": "Valido"},
        ]
        messages = _build_messages(user_message="Teste", history=history)
        # Apenas system (prompt), user valido e user message
        assert len(messages) == 3

    def test_build_messages_filters_empty_content(self):
        """Deve filtrar entradas de historico com conteudo vazio."""
        history = [
            {"role": "user", "content": "   "},
            {"role": "assistant", "content": "Ok"},
        ]
        messages = _build_messages(user_message="Teste", history=history)
        # system prompt + assistant com conteudo + user message
        assert len(messages) == 3

    def test_build_messages_strips_content(self):
        """Deve aplicar strip no conteudo das mensagens."""
        messages = _build_messages(user_message="  Ola  ", history=[])
        assert messages[1]["content"] == "Ola"


class TestBuildHeaders:
    def test_build_headers_structure(self):
        headers = _build_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        assert headers["Content-Type"] == "application/json"
        assert headers["HTTP-Referer"] == "http://localhost"
        assert headers["X-Title"] == "ChatLLM Experiment"


class TestGenerateReply:
    @pytest.mark.asyncio
    async def test_raises_config_error_without_api_key(self):
        """Deve lancar OpenRouterConfigError quando nao ha API key."""
        with patch("backend.services.openrouter.OPENROUTER_API_KEY", ""):
            with pytest.raises(OpenRouterConfigError, match="OPENROUTER_API_KEY"):
                await generate_reply(user_message="Teste", history=[])

    @pytest.mark.asyncio
    async def test_generates_reply_success(self):
        """Deve retornar o conteudo e o nome do modelo em caso de sucesso."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": "Resposta mockada"}}
            ]
        }

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("backend.services.openrouter.OPENROUTER_API_KEY", "sk-test"):
            with patch("httpx.AsyncClient", return_value=mock_client):
                reply, model = await generate_reply(
                    user_message="Ola",
                    history=[],
                    model="test-model",
                )
                assert reply == "Resposta mockada"
                assert model == "test-model"

    @pytest.mark.asyncio
    async def test_generates_reply_uses_default_model(self):
        """Deve usar o modelo default quando nao informado."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": "Resposta"}}
            ]
        }

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("backend.services.openrouter.OPENROUTER_API_KEY", "sk-test"):
            with patch("httpx.AsyncClient", return_value=mock_client):
                reply, model = await generate_reply(
                    user_message="Ola",
                    history=[],
                )
                from backend.config import OPENROUTER_MODEL_DEFAULT
                assert model == OPENROUTER_MODEL_DEFAULT

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self):
        """Deve lancar RuntimeError quando a API retorna status >= 400."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("backend.services.openrouter.OPENROUTER_API_KEY", "sk-test"):
            with patch("httpx.AsyncClient", return_value=mock_client):
                with pytest.raises(RuntimeError, match="OpenRouter retornou erro"):
                    await generate_reply(user_message="Erro", history=[])

    @pytest.mark.asyncio
    async def test_raises_on_empty_reply(self):
        """Deve lancar RuntimeError quando a resposta nao tem conteudo."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": ""}}
            ]
        }

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("backend.services.openrouter.OPENROUTER_API_KEY", "sk-test"):
            with patch("httpx.AsyncClient", return_value=mock_client):
                with pytest.raises(RuntimeError, match="nao retornou conteudo"):
                    await generate_reply(user_message="Teste", history=[])


class TestStreamReply:
    @pytest.mark.asyncio
    async def test_raises_config_error_without_api_key(self):
        """Deve lancar OpenRouterConfigError quando nao ha API key."""
        with patch("backend.services.openrouter.OPENROUTER_API_KEY", ""):
            with pytest.raises(OpenRouterConfigError, match="OPENROUTER_API_KEY"):
                async for _ in stream_reply(user_message="Teste", history=[]):
                    pass

    @staticmethod
    def _make_stream_mock(mock_aiter_lines_fn, status_code=200, aread_body=None):
        """Helper que monta o mock do stream da OpenRouter."""
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.aiter_lines = mock_aiter_lines_fn
        if aread_body is not None:
            mock_response.aread = AsyncMock(return_value=aread_body)

        class FakeStreamCtx:
            async def __aenter__(self):
                return mock_response

            async def __aexit__(self, *args):
                pass

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def stream(self, *args, **kwargs):
                return FakeStreamCtx()

        return FakeClient()

    @pytest.mark.asyncio
    async def test_yields_deltas(self):
        """Deve retornar deltas conforme o stream da OpenRouter."""
        async def mock_aiter_lines():
            yield 'data: {"choices":[{"delta":{"content":"Ola"}}]}'
            yield 'data: {"choices":[{"delta":{"content":" mundo"}}]}'
            yield "data: [DONE]"

        mock_client = self._make_stream_mock(mock_aiter_lines)

        with patch("backend.services.openrouter.OPENROUTER_API_KEY", "sk-test"):
            with patch("httpx.AsyncClient", return_value=mock_client):
                deltas = []
                async for delta in stream_reply(user_message="Teste", history=[]):
                    deltas.append(delta)

                assert deltas == ["Ola", " mundo"]

    @pytest.mark.asyncio
    async def test_handles_http_error_during_stream(self):
        """Deve lancar RuntimeError em erros HTTP durante o stream."""
        async def mock_aiter_lines():
            yield "data: x"
            if False:
                yield  # unreachable, makes it async generator

        mock_client = self._make_stream_mock(
            mock_aiter_lines, status_code=401, aread_body=b"Unauthorized"
        )

        with patch("backend.services.openrouter.OPENROUTER_API_KEY", "sk-test"):
            with patch("httpx.AsyncClient", return_value=mock_client):
                with pytest.raises(OpenRouterConfigError, match="A chave OpenRouter"):
                    async for _ in stream_reply(user_message="Teste", history=[]):
                        pass

    @pytest.mark.asyncio
    async def test_skips_invalid_json_lines(self):
        """Deve ignorar linhas com JSON invalido no stream."""
        async def mock_aiter_lines():
            yield "data: nao-e-json"
            yield 'data: {"choices":[{"delta":{"content":"valido"}}]}'
            yield "data: [DONE]"

        mock_client = self._make_stream_mock(mock_aiter_lines)

        with patch("backend.services.openrouter.OPENROUTER_API_KEY", "sk-test"):
            with patch("httpx.AsyncClient", return_value=mock_client):
                deltas = []
                async for delta in stream_reply(user_message="Teste", history=[]):
                    deltas.append(delta)

                assert deltas == ["valido"]
