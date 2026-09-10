import json

import httpx
import pytest

from backend.services import openrouter


def mock_provider(monkeypatch, response):
    client_type = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: response)
    monkeypatch.setattr(openrouter, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_type(transport=transport, **kwargs))


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("status", [404, 500])
async def test_provider_errors_are_actionable_without_private_payload(monkeypatch, streaming, status):
    message = "Model blocked by guardrail" if status == 404 else "Internal server error"
    payload = {"error": {"message": message, "metadata": {"config_url": "https://private.example/workspace"}}}
    mock_provider(monkeypatch, httpx.Response(status, json=payload))
    with pytest.raises(RuntimeError) as error:
        if streaming:
            async for _ in openrouter.stream_reply(user_message="Teste", history=[]):
                pass
        else:
            await openrouter.generate_reply(user_message="Teste", history=[])
    assert "private.example" not in str(error.value)
    assert "metadata" not in str(error.value)
    if status == 404:
        assert isinstance(error.value, openrouter.OpenRouterConfigError)
        assert "OPENROUTER_MODEL" in str(error.value)


@pytest.mark.asyncio
async def test_stream_reports_guardrail_error_inside_successful_http_response(monkeypatch):
    event = {"error": {"code": 404, "message": "Model blocked by guardrail"}}
    mock_provider(monkeypatch, httpx.Response(200, text=f"data: {json.dumps(event)}\n\n"))
    with pytest.raises(openrouter.OpenRouterConfigError, match="modelo autorizado"):
        async for _ in openrouter.stream_reply(user_message="Teste", history=[]):
            pass
