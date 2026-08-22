# Handoff

## O que está pronto

Projeto completo do desafio em monorepo:
- frontend Next.js + React + TypeScript;
- backend FastAPI + SQLAlchemy;
- PostgreSQL via Docker Compose;
- RBAC de organizador/cliente/portaria;
- catálogo Ticketmaster/TMDb;
- mapa de assentos com lock transacional;
- pagamento simulado aprovado/recusado;
- cancelamento com devolução de estoque;
- ingresso QR assinado e link público;
- validação de portaria com replay protection;
- câmera + entrada manual;
- WebSocket de assentos;
- seed;
- testes unitários;
- documentação e guia de deploy;
- checklist de cobertura;
- registro de uso de IA.

## Limitação deste ambiente

Não publiquei um repositório GitHub real porque isso exigiria acesso à conta/repositório do candidato. Também não concluí o `npm install` local durante a verificação; o processo atingiu o limite de execução do ambiente. O projeto, entretanto, inclui Docker Compose para instalar as dependências e executar tudo de forma isolada.

## Próximo passo de entrega

No repositório GitHub do candidato, faça:

```bash
git remote add origin <URL_DO_REPOSITORIO>
git push -u origin main
```

Depois configure as variáveis de ambiente do backend/frontend no provedor escolhido e publique.
