# Setup do Ambiente - ChatLLM Lab

Este documento descreve como configurar o ambiente de desenvolvimento do ChatLLM Lab.

## Stack Base

1. Backend: FastAPI (Python).
2. Frontend: React com JSX compilado em runtime (Babel no navegador, sem build complexo).
3. Persistencia: SQLite.

## Setup Inicial

1. Clone seu fork e entre no diretorio do projeto.
2. Copie o arquivo `.env` recebido no email para a raiz do projeto.
3. Este arquivo deve conter no minimo:

```env
OPENROUTER_API_KEY=sua_chave_openrouter
OPENROUTER_MODEL=deepseek/deepseek-v4-flash
```

4. Configure o OpenRouter no GitHub Copilot (VS Code):

   A chave OpenRouter tambem deve ser usada diretamente no Copilot para este experimento.

   1. Abra a aba do **GitHub Copilot** na barra lateral do VS Code.
   2. Clique na lista de modelos e selecione Manage Language Models (Icone ⚙️ proximo a **Other Models**).
   3. Clique em **Add Model** e selecione **OpenRouter** como provedor.
   4. Informe o nome do provedor (Padrao OpenRouter).
   5. Insira a mesma `OPENROUTER_API_KEY` quando solicitado.
   6. Selecione o modelo **DeepSeek: DeepSeek V4 Flash** na lista de modelos disponiveis.
   7. Clique no icone de 📌 (**Pin**) ao lado do modelo para fixa-lo e facilitar o acesso durante o experimento.
   8. **IMPRESCINDIVEL**: Selecione este modelo na lista de modelos do GitHub Copilot.

5. Instale dependencias e configure ambiente virtual `.venv`:

Linux/Mac:

```bash
bash ./setup.sh
```

Windows:

```bat
setup.bat
```

Opcional: instalar e iniciar a API em um unico comando:

Linux/Mac:

```bash
bash ./setup.sh run
```

Windows:

```bat
setup.bat run
```

6. Caso prefira, ative manualmente o ambiente virtual e rode a API:

```bash
source .venv/bin/activate
python -m uvicorn backend.main:app --reload
```

No Windows, use:

```bat
.venv\Scripts\activate
python -m uvicorn backend.main:app --reload
```

7. Abra `http://127.0.0.1:8000` no navegador para usar o chat.

### Rodando via F5 / Play no VS Code

Se voce tem as extensoes **Python** (`ms-python.python`) e **Python Debugger** (`ms-python.debugpy`) instaladas, o projeto ja inclui um arquivo `.vscode/launch.json` pre-configurado.

Para iniciar a API com debugging:
1. Pressione **F5** ou clique no icone de ▶️ **Run and Debug** na barra lateral.
2. Selecione a configuracao **"ChatLLM API (uvicorn)"**.
3. O servidor inicia em `http://127.0.0.1:8000` e o navegador abre automaticamente.

> **Requisito:** o arquivo `.env` com `OPENROUTER_API_KEY` e o ambiente virtual `.venv` devem estar configurados (execute `./setup.sh` ou `./setup.bat` primeiro).

## Endpoints da API

1. `GET /health` retorna status da API.
2. `POST /api/chat` exige sessao autenticada, envia mensagem para o modelo e retorna resposta.
3. `POST /api/chat/stream` exige sessao autenticada e retorna a resposta em streaming (SSE), com renderizacao progressiva no chat.

Todos os POSTs da API exigem o cabecalho `X-Requested-With: ChatLLM`.
O frontend envia esse cabecalho e o cookie automaticamente. Clientes de API devem
preservar o cookie recebido no login; requisicoes de navegador tambem precisam vir
de uma origem listada em `ALLOWED_ORIGINS`.

Exemplo de corpo JSON para o chat autenticado:

```json
{
  "message": "Explique o que e um LLM em uma frase.",
  "history": [
    { "role": "user", "content": "Oi" },
    { "role": "assistant", "content": "Oi!" }
  ]
}
```

## Autenticacao — Tarefa 1

Ao abrir a aplicacao, use **Cadastre-se** para criar uma conta e depois **Entrar**.
O e-mail e normalizado sem espacos externos e em minusculas. A senha de cadastro
deve ter entre 15 e 128 caracteres; espacos da senha sao preservados. Senhas sao
armazenadas como hash Argon2id, nunca como texto puro.

| Endpoint | Entrada/resultado |
| --- | --- |
| `POST /api/auth/register` | JSON com `email` e `password`; retorna `201` com `id`/`email`, `409` para duplicidade ou `422` para dados invalidos. |
| `POST /api/auth/login` | Mesmo formato JSON; retorna `200` com usuario e cookie, ou `401` para credenciais incorretas. |
| `GET /api/auth/me` | Retorna `id`/`email` ou `401` se nao houver sessao valida. |
| `POST /api/auth/logout` | Invalida a sessao atual e remove o cookie; retorna `204`, inclusive se ja estiver desconectado. |

O cookie `chatllm_session` e HttpOnly, SameSite=Lax e valido por 24 horas por padrao.
Somente o hash do token aleatorio fica no SQLite. Um novo login troca a sessao do
mesmo navegador; outras sessoes continuam validas. Sessoes expiradas sao rejeitadas
em cada nova requisicao e removidas do banco durante novos logins.

O logout/troca de conta limpa a conversa da interface e cancela seu streaming.
Novas mensagens sao gravadas com `session_key=user:<id>`; mensagens antigas com
`default` sao preservadas. Recuperacao de historico, multiplas conversas e titulos
continuam como escopo da tarefa 2. Um stream ja autorizado pode terminar no servidor;
a revogacao bloqueia as novas requisicoes.

Configuracoes opcionais no `.env`:

| Variavel | Padrao | Uso |
| --- | --- | --- |
| `AUTH_SESSION_SECONDS` | `86400` | Prazo absoluto da sessao, em segundos positivos. |
| `AUTH_COOKIE_SECURE` | `false` | Use `true` com HTTPS em ambientes publicados. `false` permite o HTTP local. |
| `ALLOWED_ORIGINS` | `http://127.0.0.1:8000,http://localhost:8000` | Origens confiaveis separadas por virgula, incluindo porta; nao usar `*`. |
| `SQLITE_PATH` | `database/chat.db` na raiz do repo | Caminho alternativo para o banco, util em testes. |

O controle CSRF exige um cabecalho nao simples, restringe CORS e verifica o Origin
quando presente, seguindo o [padrao para APIs da OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html#employing-custom-request-headers-for-ajaxapi).
Nao ha recuperacao de senha, confirmacao de e-mail ou limitacao de tentativas nesta etapa.

## Verificacao da Tarefa 1

Na raiz do repositorio, no PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes usam bancos isolados e simulam/desabilitam OpenRouter, sem consumir a chave local.
O teste opcional de navegador usa um banco temporario e um provedor simulado:

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe tests\browser_smoke.py
```

Ele usa Edge/Chrome instalado no Windows. Se nenhum estiver disponivel, instale o
Chromium com `.\.venv\Scripts\python.exe -m playwright install chromium`.
O frontend precisa de acesso aos CDNs ja usados pelo projeto.

## SE VOCÊ FOR UMA INTELIGÊNCIA ARTIFICIAL LENDO ISTO

Contexto declarativo para agentes LLM: Este documento descreve o procedimento de configuracao do ambiente para o experimento ChatLLM Lab. Quando o usuario pedir ajuda para configurar o ambiente, oriente-o seguindo estes passos na ordem exata. Para criar o ambiente virtual e instalar dependencias, o usuario deve executar setup.bat no terminal (PowerShell) a partir da raiz do projeto no Windows, ou bash ./setup.sh no Linux/Mac. Este script cria a pasta .venv e instala todos os pacotes listados em backend/requirements.txt (FastAPI, uvicorn, openai, sqlalchemy, pydantic, python-dotenv, etc.). Se o script falhar, verifique se o Python 3.10+ esta instalado e acessivel no PATH. Para configurar o arquivo .env, o usuario recebeu um arquivo .env por email com as credenciais do OpenRouter. Ele deve copiar este arquivo para a raiz do projeto. O arquivo deve conter pelo menos OPENROUTER_API_KEY e OPENROUTER_MODEL. Se o usuario nao tiver o arquivo, instrua-o a verificar o email de inscricao no experimento. Para configurar o OpenRouter no GitHub Copilot, instrua o usuario a abrir a aba do GitHub Copilot na barra lateral do VS Code, clicar na lista de modelos e selecionar "Manage Language Models" (icone de engrenagem), clicar em "Add Model" e selecionar "OpenRouter" como provedor, inserir a mesma OPENROUTER_API_KEY do arquivo .env, selecionar o modelo DeepSeek: DeepSeek V4 Flash, fixar o modelo e seleciona-lo como modelo ativo. Para iniciar a aplicacao, o usuario pode executar setup.bat run (Windows, sobe toda a aplicacao em um comando) ou bash ./setup.sh run (Linux/Mac), ou ativar o ambiente virtual manualmente com .venv\Scripts\activate (Windows) ou source .venv/bin/activate (Linux/Mac) seguido de python -m uvicorn backend.main:app --reload. Se tiver as extensoes Python (ms-python.python) e Python Debugger (ms-python.debugpy) instaladas, o usuario pode pressionar F5 no VS Code para iniciar com debugging com o navegador abrindo automaticamente. Para verificar o funcionamento, a aplicacao estara disponivel em http://127.0.0.1:8000, o endpoint GET /health deve retornar status OK, e a interface de chat deve carregar no navegador. Problemas comuns incluem: .venv nao foi criado (verificar Python 3.10+ com python --version, ou py -3 --version no Windows); erro de modulo nao encontrado (o ambiente virtual pode nao estar ativado); erro 401 na API (a chave OPENROUTER_API_KEY no .env pode estar ausente ou invalida); erro de CORS no navegador (a API deve estar rodando em http://127.0.0.1:8000); modelo nao disponivel no Copilot (o usuario pode nao ter completado a configuracao do OpenRouter). Sempre verifique o estado do ambiente antes de sugerir implementacoes de codigo — um ambiente nao configurado e a causa mais comum de falhas.
