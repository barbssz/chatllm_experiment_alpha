"""Teste opcional da interface real, com banco temporario e OpenRouter simulado.

Instalar: python -m pip install playwright
Executar: python tests/browser_smoke.py
Usa Edge/Chrome instalado ou Chromium do Playwright, sempre sem janela.
"""
from __future__ import annotations

import asyncio
from contextlib import closing
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def serve(port: int) -> None:
    import uvicorn
    from backend.main import app
    import backend.routers.chat as chat

    async def reply(**kwargs):
        return "Resposta de teste.", "mock-model"

    async def stream(**kwargs):
        yield "Resposta "
        await asyncio.sleep(30 if kwargs["user_message"] == "demorar" else 0.1)
        yield "de teste."

    chat.generate_reply = reply
    chat.stream_reply = stream
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def smoke() -> None:
    from playwright.sync_api import sync_playwright, expect

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(
        prefix="chatllm-browser-", ignore_cleanup_errors=True
    ) as temp:
        database = str(Path(temp) / "chat.db")
        env = {**os.environ, "SQLITE_PATH": database, "OPENROUTER_API_KEY": "",
               "AUTH_COOKIE_SECURE": "false", "ALLOWED_ORIGINS": origin}
        server = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--serve", str(port)],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError(server.stderr.read().decode(errors="replace"))
                try:
                    with urlopen(f"{origin}/health", timeout=0.5) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Servidor de teste nao iniciou.")

            with sync_playwright() as playwright:
                browser_path = next((path for path in (
                    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
                    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
                ) if path.exists()), None)
                browser = playwright.chromium.launch(
                    headless=True, **({"executable_path": str(browser_path)} if browser_path else {})
                )
                context = browser.new_context(viewport={"width": 1280, "height": 800})
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.set_default_timeout(20000)
                page.goto(origin)
                expect(page.get_by_role("heading", name="Entre para conversar")).to_be_visible()
                password = "uma frase secreta 123"

                def register(email):
                    page.get_by_role("button", name="Ainda não tem conta? Cadastre-se").click()
                    page.get_by_label("E-mail", exact=True).fill(email)
                    page.get_by_label("Senha", exact=True).fill(password)
                    page.get_by_role("button", name="Criar conta", exact=True).click()
                    expect(page.get_by_text("Conta criada! Entre com seu e-mail e senha.")).to_be_visible()

                def login(email):
                    page.get_by_label("E-mail", exact=True).fill(email)
                    page.get_by_label("Senha", exact=True).fill(password)
                    page.get_by_role("button", name="Entrar", exact=True).click()
                    expect(page.locator(".account-email")).to_have_text(email)

                register("alice@example.com")
                page.get_by_label("Senha", exact=True).fill("senha incorreta")
                page.get_by_role("button", name="Entrar", exact=True).click()
                expect(page.get_by_role("alert")).to_contain_text("E-mail ou senha incorretos")
                login("alice@example.com")
                assert "chatllm_session" not in page.evaluate("document.cookie")
                cookie = next(item for item in context.cookies() if item["name"] == "chatllm_session")
                assert cookie["httpOnly"] and cookie["sameSite"] == "Lax"
                page.reload()
                expect(page.locator(".account-email")).to_have_text("alice@example.com")
                page.get_by_placeholder("Mensagem para ChatLLM Lab").fill("Mensagem privada de Alice")
                page.get_by_role("button", name="Enviar", exact=True).click()
                expect(page.locator(".bubble.assistant").last).to_contain_text("Resposta de teste.")
                expect(page.get_by_role("button", name="Enviar", exact=True)).to_be_visible()

                # Tarefa 2: sessoes com titulo automatico na barra lateral.
                expect(page.locator(".sidebar-item")).to_have_count(1)
                expect(page.locator(".sidebar-item").first).to_have_text("Mensagem privada de Alice")
                page.get_by_role("button", name="+ Nova conversa").click()
                expect(page.locator(".bubble")).to_have_count(1)
                page.get_by_placeholder("Mensagem para ChatLLM Lab").fill("Segunda conversa de Alice")
                page.get_by_role("button", name="Enviar", exact=True).click()
                expect(page.locator(".bubble.assistant").last).to_contain_text("Resposta de teste.")
                expect(page.locator(".sidebar-item")).to_have_count(2)
                expect(page.locator(".sidebar-item").first).to_have_text("Segunda conversa de Alice")
                page.locator(".sidebar-item").nth(1).click()
                expect(page.get_by_text("Mensagem privada de Alice", exact=True)).to_have_count(1)

                page.get_by_placeholder("Mensagem para ChatLLM Lab").fill("demorar")
                page.get_by_role("button", name="Enviar", exact=True).click()
                expect(page.get_by_role("button", name="Parar", exact=True)).to_be_visible()
                page.get_by_role("button", name="Parar", exact=True).click()
                expect(page.get_by_role("button", name="Enviar", exact=True)).to_be_visible()
                page.get_by_role("button", name="Sair", exact=True).click()
                expect(page.get_by_role("heading", name="Entre para conversar")).to_be_visible()
                assert not any(item["name"] == "chatllm_session" for item in context.cookies())

                # Cadastro duplicado tem feedback e nao cria uma segunda conta.
                page.get_by_role("button", name="Ainda não tem conta? Cadastre-se").click()
                page.get_by_label("E-mail", exact=True).fill("alice@example.com")
                page.get_by_label("Senha", exact=True).fill(password)
                page.get_by_role("button", name="Criar conta", exact=True).click()
                expect(page.get_by_role("alert")).to_contain_text("ja esta cadastrado")
                page.get_by_role("button", name="Já tem conta? Entrar").click()
                register("bob@example.com")
                login("bob@example.com")
                expect(page.get_by_text("Mensagem privada de Alice", exact=True)).to_have_count(0)
                expect(page.locator(".bubble")).to_have_count(1)

                # Uma sessao expirada provoca 401 e desmonta a conversa.
                with closing(sqlite3.connect(database)) as db:
                    db.execute("UPDATE auth_sessions SET expires_at = '2000-01-01 00:00:00'")
                    db.commit()
                page.get_by_placeholder("Mensagem para ChatLLM Lab").fill("Sessao expirada")
                page.get_by_role("button", name="Enviar", exact=True).click()
                expect(page.get_by_text("Sua sessão expirou. Entre novamente para continuar.")).to_be_visible()
                login("bob@example.com")
                page.get_by_placeholder("Mensagem para ChatLLM Lab").fill("demorar")
                page.get_by_role("button", name="Enviar", exact=True).click()
                expect(page.get_by_role("button", name="Parar", exact=True)).to_be_visible()
                page.get_by_role("button", name="Sair", exact=True).click()
                expect(page.get_by_role("heading", name="Entre para conversar")).to_be_visible()

                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                expect(page.get_by_role("button", name="Entrar", exact=True)).to_be_visible()
                assert not errors, errors
                browser.close()
                print("Browser smoke: cadastro, duplicidade, login, cookie, reload, streaming, parar, logout, troca de conta, expiracao, sessoes com titulo automatico e layout mobile OK.")
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
            server.stderr.close()
            # No Windows o SQLite pode manter chat.db bloqueado por alguns
            # instantes apos o processo encerrar; aguardamos o lock ser liberado
            # para que a limpeza do diretorio temporario nao falhe.
            for attempt in range(20):
                try:
                    Path(database).unlink(missing_ok=True)
                    break
                except PermissionError:
                    if attempt == 19:
                        raise
                    time.sleep(0.1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        serve(int(sys.argv[2]))
    else:
        smoke()
