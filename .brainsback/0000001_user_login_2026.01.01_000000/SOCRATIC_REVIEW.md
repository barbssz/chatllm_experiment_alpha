# Socratic Review

**Modelo da IA:** DeepSeek V4 Flash
**Data:** 2026-09-10

# Parte A — Tarefa 1 (Login/Logout)

## Pergunta 1 — O que foi implementado?

**Pergunta:** O que foi implementado nesta tarefa?

**Resposta:** Foi implementado cadastro, login e logout por e-mail e senha, com usuários e sessões persistidos no SQLite. As senhas são protegidas com Argon2id, e as duas rotas do chat exigem uma sessão válida. A interface ganhou formulários de autenticação e botão de saída, preservando o streaming das respostas.

## Pergunta 2 — Explicação de Módulos

**Pergunta:** Explique como os módulos `backend/routers/auth.py`, `backend/services/auth.py` e `backend/dependencies.py` interagem entre si — quais funções chamam quais e como os dados fluem desde uma requisição HTTP até a resposta.

**Resposta:** O `backend/routers/auth.py` recebe as requisições HTTP de cadastro, login, logout e consulta do usuário. Ele usa os schemas para validar os dados e chama as funções de `backend/services/auth.py`, que concentra a lógica de autenticação.

- **Cadastro:** `register()` chama `hash_password()`, salva o usuário no SQLite e retorna `id` e e-mail com status `201`.
- **Login:** `login()` chama `authenticate_user()`, que busca o usuário e verifica a senha com Argon2id. Se estiver correta, chama `create_session()`, que grava o hash de um token aleatório e sua expiração no banco. A rota coloca o token original no cookie HttpOnly e retorna os dados públicos do usuário.
- **Requisição autenticada:** o FastAPI executa `get_current_user()`, de `dependencies.py`, por meio de `Depends`. Essa função lê o cookie e chama `user_for_session()`, do serviço. Se a sessão estiver válida, entrega o usuário à rota; caso contrário, retorna `401`. Isso protege `/me` e as duas rotas do chat.
- **Logout:** `logout()` chama `revoke_session()`, confirma a exclusão no banco, apaga o cookie e retorna `204`.

O `dependencies.py` também fornece `require_csrf_protection()`, que verifica o cabeçalho de segurança e a origem dos POSTs. A conexão com o banco é fornecida por `get_db()`, de `backend/database.py`, via injeção de dependência.

## Pergunta 3 — Autonomia de Depuração

**Pergunta:** Um usuário relata que, ao dar dois cliques rápidos em "Criar conta", às vezes aparece um erro interno do servidor (500) em vez da mensagem de e-mail já cadastrado (409). Como você investigaria e resolveria esse problema sem auxílio de ferramentas de IA?

**Resposta:** Eu começaria reproduzindo o problema e verificando, na aba Network do navegador, se os dois cliques enviam duas requisições. Depois consultaria o traceback no backend para identificar a causa do `500`.

Minha principal suspeita seria uma **condição de corrida**: as duas requisições consultam o e-mail antes de qualquer uma concluir o cadastro. Ambas encontram o endereço disponível, mas a segunda inserção viola a restrição `UNIQUE`.

Para confirmar, enviaria duas requisições simultâneas com o mesmo e-mail e verificaria se a exceção é `IntegrityError`. No nosso código já existe tratamento dessa exceção no `commit()`, então também conferiria se o servidor está executando a versão atual e se a falha ocorre nesse trecho. Se o erro for `database is locked`, investigaria as transações do SQLite separadamente.

A correção seria manter a restrição `UNIQUE` no banco e tratar especificamente o conflito de e-mail: executar `rollback()` e retornar `409`. No frontend, bloquearia novos envios enquanto o cadastro estiver pendente, mas manteria a proteção no backend.

Por fim, criaria um teste com dois cadastros simultâneos: o resultado esperado seria **um `201`, um `409` e apenas um usuário no banco**.

## Pergunta 4 — Justificativa de Lógica

**Pergunta:** Justifique a decisão de guardar apenas o hash SHA-256 do token de sessão no banco, em vez de armazenar o token em si — ou, alternativamente, em vez de adotar um token sem estado (como JWT).

**Resposta:** O token de sessão funciona como uma credencial: quem possui seu valor pode se autenticar. Por isso, guardamos apenas seu **hash SHA-256** no banco. Se houver vazamento somente do banco, o atacante não poderá usar diretamente esse hash como cookie para entrar na conta.

O token original é gerado aleatoriamente, com 256 bits de entropia, e enviado ao navegador. A cada requisição, calculamos seu hash e buscamos a sessão correspondente, verificando a expiração. SHA-256 é adequado nesse caso porque o token é imprevisível; senhas humanas precisam de um algoritmo mais resistente a tentativas de adivinhação, como Argon2id.

Escolhemos sessões no banco porque **simplificam a revogação no logout**: basta excluir a sessão. Um JWT sem estado normalmente continua válido até expirar; invalidá-lo antes disso exigiria algum controle adicional, como uma lista de revogação.

O custo dessa escolha é consultar o banco nas requisições autenticadas, uma troca aceitável para o tamanho e os requisitos deste projeto.

## Pergunta 5 — Capacidade de Onboarding

**Pergunta:** Se um novo desenvolvedor entrasse no projeto agora, você conseguiria explicar a lógica interna desta funcionalidade sem que ele precisasse ler cada linha gerada por IA?

**Resposta:**
- **Fluxo de dados:** no cadastro, o backend valida e normaliza o e-mail, gera o hash da senha e salva o usuário. No login, verifica a senha, cria uma sessão no banco e envia o token em um cookie. Nas chamadas ao chat, valida essa sessão antes de acessar o OpenRouter. No logout, exclui a sessão e apaga o cookie.
- **Responsabilidade dos módulos:** os schemas validam entradas; `routers/auth.py` recebe as requisições e monta as respostas; `services/auth.py` cuida de senhas e sessões; `dependencies.py` verifica autenticação e proteção CSRF; os modelos representam os dados persistidos. O frontend apresenta os formulários e controla a exibição do chat.
- **Invariantes:** e-mails normalizados devem ser únicos; senhas e tokens de sessão não são armazenados em texto puro; sessões inválidas, expiradas ou revogadas não autorizam novas chamadas ao chat; respostas públicas não expõem hashes. Ao sair ou trocar de conta, a interface descarta a conversa anterior.
- **Decisões críticas:** Argon2id protege senhas; SHA-256 protege tokens aleatórios de alta entropia. Sessões no SQLite permitem revogação direta, ao custo de consultar o banco. O cookie HttpOnly dificulta a leitura do token por JavaScript; cabeçalho adicional e CORS restrito protegem contra CSRF. A interface cancela o streaming ao sair, mas uma requisição já autorizada pode terminar no servidor.

## Pergunta 6 — Encerramento

**Pergunta:** Você está satisfeito com o resultado desta implementação?

**Resposta:** Estou satisfeito com o resultado para o escopo da tarefa: cadastro, login, logout e proteção do chat funcionam, com testes automatizados e validação no navegador.

Ainda há limitações: não temos limitação de tentativas de login, recuperação de senha ou confirmação de e-mail. As sessões expiradas só são removidas durante novos logins, e um streaming já autorizado pode terminar no servidor após o logout.

Eu faria diferente na validação inicial: testaria mais cedo a integração real com o OpenRouter, porque os testes simulados não identificaram o bloqueio do modelo pelo workspace.

Como próximos passos, priorizaria limitar tentativas de autenticação, testar cadastros simultâneos e automatizar a limpeza das sessões expiradas. Para publicar, configuraria HTTPS e cookie `Secure`. Histórico e múltiplas conversas ficam para a tarefa 2.

---

# Avaliação

## Revisão Reflexiva

O desenvolvedor demonstrou modelo mental consistente da funcionalidade, articulando com precisão o fluxo de dados entre roteadores, serviços, dependências e modelos persistidos, bem como as invariantes do sistema (unicidade de e-mail normalizado, ausência de senhas/tokens em texto puro, rejeição de sessões inválidas/expiradas/revogadas e não exposição de hashes em respostas públicas). Reconheceu limitações reais do incremento e apontou melhorias futuras específicas e coerentes com o código.

## Debate Socrático

**Pergunta 1 — O que foi implementado?**
Resposta correta e alinhada ao escopo: cadastro/login/logout por e-mail e senha, persistência em SQLite, senhas com Argon2id, rotas de chat protegidas e preservação do streaming.
Avaliação técnica: Adequada. Descreveu o escopo sem confundir com a Tarefa 2 (sessões/títulos), que permanece fora deste incremento.

**Pergunta 2 — Explicação de Módulos**
Resposta correta. Descreveu a separação de responsabilidades (roteador → serviço → dependência), os endpoints e o caminho de `get_current_user`→`user_for_session`, além do `require_csrf_protection` e do `get_db`.
Avaliação técnica: Correta. Demonstrou compreensão da direção das dependências e do ponto em que a autenticação é imposta antes das chamadas ao OpenRouter.

**Pergunta 3 — Autonomia de Depuração**
Resposta correta e completa. Identificou corretamente a condição de corrida entre o pré-check e a constraint `UNIQUE`, propôs confirmar via `IntegrityError`, manter a invariante no banco, tratar o conflito com `rollback()`+`409` e adicionar teste de concorrência.
Avaliação técnica: Correta. Reconheceu que a proteção deve residir no banco (constraint), não apenas no pré-check da aplicação — exatamente o ponto frágil do código.

**Pergunta 4 — Justificativa de Lógica**
Resposta correta. Justificou o hashing do token por ser credencial bearer, distinguiu SHA-256 (token de alta entropia) de Argon2id (senha humana) e comparou sessão em banco (revogação imediata) com JWT stateless (exige denylist), citando o custo da consulta por requisição.
Avaliação técnica: Correta. Demonstrou entender a propriedade de segurança central (vazamento do banco não permite forjar cookie) e o trade-off de revogabilidade.

**Pergunta 5 — Capacidade de Onboarding**
Resposta completa. Cobriu fluxo de dados, responsabilidades por módulo, invariantes e decisões de design (Argon2id, SHA-256, HttpOnly, CSRF/CORS), inclusive a ressalva de que um stream já autorizado pode concluir no servidor após o logout.
Avaliação técnica: Correta. Explicou a arquitetura em alto nível, sem depender de leitura linha a linha do código gerado.

**Pergunta 6 — Encerramento**
Resposta adequada. Reconheceu limitações (sem rate limiting, recuperação de senha ou verificação de e-mail; limpeza de sessões só no login; stream residual), identificou o aprendizado sobre testar a integração real mais cedo e priorizou próximos passos pertinentes.
Avaliação técnica: Correta. Autocrítica honesta e alinhada às limitações registradas no `REPORT.md`.

## Veredito

**Status:** MASTERY PROVEN

O desenvolvedor respondeu às seis perguntas de forma correta, coerente com o código e o `REPORT.md`, demonstrando domínio do fluxo de autenticação, das invariantes de segurança e dos trade-offs de design. A implementação da Tarefa 1 é considerada concluída sob o pipeline Mastery-Aware.


