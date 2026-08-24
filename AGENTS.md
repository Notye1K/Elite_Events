# Elite Events - Contexto do Projeto

## Objetivo
Desafio técnico Elite Dev 2026.

Plataforma de eventos e ingressos onde:
- Organizador cria e gerencia eventos
- Cliente reserva, paga e recebe ingresso
- Portaria valida ingresso por QR code

## Stack

### Frontend
- Next.js 16
- React
- TypeScript
- App Router
- Deploy: Vercel

### Backend
- Python 3.12
- FastAPI
- SQLAlchemy
- Pydantic
- psycopg 3
- Deploy: Render

### Banco
- PostgreSQL
- Produção: Supabase
- Local: PostgreSQL via Docker Compose

## Docker

Execução normal:
docker compose up --build

Desenvolvimento:
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

No modo dev:
- Next usa hot reload
- FastAPI usa uvicorn --reload
- frontend e backend são montados como volumes

## Deploy

### Frontend
Vercel
Root Directory:
frontend

### Backend
Render
Root Directory:
backend

### Database
Supabase PostgreSQL

No Render NÃO usar Direct Connection do Supabase, pois pode resolver para IPv6.

Usar:
Supabase Session Pooler
porta 5432

## PostgreSQL / SQLAlchemy

O projeto usa psycopg 3.

DATABASE_URL pode vir como:
postgresql://...

O backend normaliza para:
postgresql+psycopg://...

Não usar psycopg2.

## Configuração já corrigida

Em backend/app/config.py:

field_validator vem de:

from pydantic import field_validator

E não de:

from pydantic_settings import field_validator

## Segurança

Nunca versionar:
- .env
- senhas
- DATABASE_URL real
- tokens
- .venv

Versionar:
- .env.example
- requirements.txt
- package.json
- package-lock.json

## Frontend / autenticação

O login salva:
- token
- user

em localStorage.

Queremos que o header:
- mostre "Entrar" quando não autenticado
- mostre um menu do usuário quando autenticado
- mostre nome e role
- permita logout
- ao logout limpe sessão e redirecione para /login

## Roles

Existem 3 roles:
- client → Cliente
- organizer → Organizador
- gate → Portaria

Idealmente o menu principal deve mostrar apenas opções pertinentes ao role.

## Funcionalidades

Obrigatórias:
- autenticação por roles
- eventos
- integração com API externa
- reserva
- prevenção de venda dupla
- pagamento simulado aprovado/recusado
- ingresso com QR assinado
- compartilhamento
- portaria
- impedir uso duplicado

Opcionais implementados ou planejados:
- filtros
- painel do organizador
- cancelamento com devolução ao estoque
- assentos em tempo real
- WebSocket
- Docker Compose
- testes
- deploy
- documentação

## Deploy já enfrentado

Problemas corrigidos:
1. SQLAlchemy tentou usar psycopg2
2. field_validator estava importado do módulo errado
3. Render não alcançava Supabase Direct Connection via IPv6
4. solução: Supabase Session Pooler IPv4

## Forma de trabalhar

Antes de alterar código:
1. ler os arquivos relacionados
2. entender a implementação atual
3. evitar reescrever partes não relacionadas
4. manter compatibilidade com Docker, Render e Vercel
5. rodar testes/build relevantes após mudanças

Quando alterar dependências:
Frontend:
- atualizar package.json
- atualizar package-lock.json

Backend:
- atualizar requirements.txt

Não adicionar .venv ao Git.

## Git

Usar commits descritivos com Conventional Commits, por exemplo:
- feat:
- fix:
- chore:
- docs:
- test:

Evitar commits genéricos como:
- update
- changes
- final