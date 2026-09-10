# Strategic Blueprint

> Focus on the **what** and **why**. The code will follow.

**Hard rule**: AI agents must not edit this file and must not draft paste-ready content for it.

## The Problem
_State clearly what you are trying to achieve and the architectural constraints, avoiding implementation specifics of HOW to do it. Focus on WHAT and WHY._
Devo explicar que o chat atualmente permite acesso sem autenticação e que você quer adicionar cadastro, entrada e saída por e-mail e senha. Os usuários devem continuar cadastrados após reiniciar a aplicação. Manter FastAPI, React e SQLite.

## Steps
- [Dividir o trabalho em: modelar usuários e sessões; implementar cadastro; implementar login e identificação do usuário; implementar logout; proteger as rotas do chat; integrar os formulários na interface; executar testes e conferir o funcionamento no navegador. ] _Decompose the problem into actionable logical steps._
- [ ] _Each step should represent a verifiable piece of work._

## Success Looks Like
- [cadastro válido funciona; 
e-mail duplicado é rejeitado; 
senha incorreta não autentica; 
usuário conectado consegue conversar; 
acesso sem autenticação recebe 401; 
logout invalida a sessão; 
cadastro permanece após reiniciar o servidor. ] _Define rigorous, observable criteria for success. E.g., The endpoint returns 200 OK with the user object, NOT Code compiles_

## Notes
- [hash Argon2id;
 e-mail único com normalização consistente; 
 sessão com expiração; cookie protegido; mensagem genérica para credenciais incorretas;
  preservação do streaming existente. ] _Any specific edge cases, libraries to consider, or potential pitfalls._

---
**⚠️ HUMAN ONLY**: This file is your strategic space. AI agents must not edit it.
