# Handoff

## O que está pronto

Projeto completo do desafio em monorepo:
- frontend Next.js + React + TypeScript;
- backend FastAPI + SQLAlchemy;
- PostgreSQL via Docker Compose;
- RBAC de organizador/cliente/portaria;
- catálogos externos TMDb (filmes) e Ticketmaster (shows);
- mapa de 200 assentos para filmes e estoque geral para shows, ambos com lock transacional;
- Stripe Checkout em sandbox, com cartões de teste, webhook assinado e reserva temporária;
- cancelamento com devolução de estoque;
- ingresso QR assinado e link público;
- validação de portaria com replay protection;
- câmera + entrada manual;
- WebSocket de assentos;
- seed;
- testes automatizados, incluindo concorrência no PostgreSQL;
- documentação e guia de deploy;
- checklist de cobertura;
- registro de uso de IA e arquivo de contexto `AGENTS.md`;
- CI no GitHub Actions para frontend, backend e Docker Compose.

## Publicação

O frontend está publicado em [https://frontend-iota-ashy-55.vercel.app/](https://frontend-iota-ashy-55.vercel.app/). A Vercel e o Render fazem o deploy automaticamente a partir da branch conectada; o GitHub Actions executa as verificações de CI antes da entrega.

## Próximo passo antes da entrega

Confirme que todas as alterações locais foram versionadas e enviadas ao repositório público:

```bash
git status
git push origin main
```

Depois, confira o CI no GitHub, o deploy do Render e o deploy da Vercel.
