from __future__ import annotations

import json

import httpx

from backend.config import OPENROUTER_API_KEY, OPENROUTER_API_URL, OPENROUTER_MODEL_DEFAULT


class OpenRouterConfigError(RuntimeError):
    pass


def _provider_error(status: int, body: str) -> RuntimeError:
    # Os detalhes do provedor podem conter URLs privadas e metadados do workspace.
    # Classificamos o problema sem devolver o payload bruto para a interface.
    if "guardrail" in body.lower():
        return OpenRouterConfigError(
            "O modelo configurado foi bloqueado pelas regras do workspace OpenRouter. "
            "Configure OPENROUTER_MODEL com um modelo autorizado e reinicie o servidor."
        )
    if status in (401, 403):
        return OpenRouterConfigError("A chave OpenRouter nao foi aceita ou nao possui permissao para esta chamada.")
    if status == 402:
        return OpenRouterConfigError("O saldo ou limite de uso do OpenRouter foi atingido.")
    if status == 429:
        return RuntimeError("O OpenRouter esta limitando as requisicoes. Aguarde e tente novamente.")
    return RuntimeError(f"OpenRouter retornou erro {status}. Tente novamente mais tarde.")


_SYSTEM_PROMPT = (
    "Keep your answers short and concise. "
    "When writing mathematical expressions, use LaTeX notation: "
    r"\( ... \) for inline math and $$ ... $$ for display/block math. "
    "When writing currency values (e.g. dollar amounts), always escape the dollar sign as the HTML entity &#36; "
    "(e.g. write &#36;5.00 instead of $5.00) so it is never confused with a LaTeX delimiter."
)


def _build_messages(*, user_message: str, history: list[dict]) -> list[dict]:
    messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for item in history:
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content.strip()})

    messages.append({"role": "user", "content": user_message.strip()})
    return messages


def _build_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "ChatLLM Experiment",
    }


async def generate_reply(*, user_message: str, history: list[dict], model: str | None = None) -> tuple[str, str]:
    if not OPENROUTER_API_KEY:
        raise OpenRouterConfigError(
            "OPENROUTER_API_KEY nao definido. Configure em .env ou environment variables."
        )

    resolved_model = model or OPENROUTER_MODEL_DEFAULT
    messages = _build_messages(user_message=user_message, history=history)

    payload = {
        "model": resolved_model,
        "messages": messages,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(OPENROUTER_API_URL, json=payload, headers=_build_headers())

    if response.status_code >= 400:
        raise _provider_error(response.status_code, response.text)

    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

    reply = content.strip()
    if not reply:
        raise RuntimeError("OpenRouter nao retornou conteudo de resposta.")

    return reply, resolved_model


async def stream_reply(*, user_message: str, history: list[dict], model: str | None = None):
    if not OPENROUTER_API_KEY:
        raise OpenRouterConfigError(
            "OPENROUTER_API_KEY nao definido. Configure em .env ou environment variables."
        )

    resolved_model = model or OPENROUTER_MODEL_DEFAULT
    payload = {
        "model": resolved_model,
        "messages": _build_messages(user_message=user_message, history=history),
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        async with client.stream("POST", OPENROUTER_API_URL, json=payload, headers=_build_headers()) as response:
            if response.status_code >= 400:
                body = await response.aread()
                raise _provider_error(response.status_code, body.decode(errors="replace"))

            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue

                data = line[len("data:") :].strip()
                if data == "[DONE]":
                    break

                try:
                    parsed = json.loads(data)
                except json.JSONDecodeError:
                    continue

                if parsed.get("error"):
                    error = parsed["error"]
                    code = error.get("code", 502) if isinstance(error, dict) else 502
                    raise _provider_error(code, json.dumps(error))

                delta = parsed.get("choices", [{}])[0].get("delta", {}).get("content")
                if isinstance(delta, str) and delta:
                    yield delta
