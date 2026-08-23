# Deploy rápido — Elite Dev

## Arquitetura

```text
Vercel (Next.js)
       │ HTTPS / WSS
       ▼
Render Free (FastAPI + Docker)
       │ TLS PostgreSQL
       ▼
Supabase Free (PostgreSQL)
```

## Passo a passo

### A. GitHub

1. Crie um repositório público.
2. Faça push da pasta inteira deste projeto.
3. Não publique um `.env` real. Use apenas `.env.example`.

### B. Supabase

1. Crie um projeto.
2. Copie a conexão PostgreSQL.
3. Transforme o prefixo em `postgresql+psycopg://`.
4. Adicione `?sslmode=require` quando a conexão exigir SSL.

### C. Render

1. New → Web Service.
2. Selecione o repositório.
3. Root Directory: `backend`.
4. Runtime: Docker.
5. Plan: Free.
6. Health Check Path: `/health`.
7. Configure:

```text
DATABASE_URL
JWT_SECRET
TICKET_SECRET
FRONTEND_URL
CORS_ORIGINS
TMDB_API_KEY (opcional)
```

8. Faça o deploy.
9. Confirme `https://SEU-BACKEND/health`.

### D. Vercel

1. New Project.
2. Selecione o mesmo repositório.
3. Root Directory: `frontend`.
4. Framework: Next.js.
5. Configure:

```text
NEXT_PUBLIC_API_URL=https://SEU-BACKEND.onrender.com
```

6. Deploy.

### E. Voltar ao Render

Atualize:

```text
FRONTEND_URL=https://SEU-FRONTEND.vercel.app
CORS_ORIGINS=https://SEU-FRONTEND.vercel.app
```

Faça redeploy da API.

## Smoke test

1. Frontend abre.
2. Login cliente: `cliente1@elite.dev` / `123456`.
3. Evento seed aparece.
4. Assento pode ser selecionado.
5. Pagamento aprovado cria ingresso.
6. QR aparece em **Meus ingressos**.
7. Login portaria: `portaria@elite.dev` / `123456`.
8. Validação retorna `valid`.
9. Segunda validação retorna `already_used`.

## Se o backend parecer lento

A primeira chamada depois de um período sem tráfego pode acordar o serviço gratuito. Aguarde e recarregue a página; isso não indica erro da aplicação por si só.
