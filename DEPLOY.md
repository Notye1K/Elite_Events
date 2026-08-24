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

## Smoke test

1. Frontend abre.
2. Login cliente: `cliente1@elite.dev` / `123456`.
3. Evento seed aparece.
4. Assento pode ser selecionado.
5. Checkout Stripe aprovado e confirmado pelo webhook cria o ingresso.
6. QR aparece em **Meus ingressos**.
7. Login portaria: `portaria@elite.dev` / `123456`.
8. Validação retorna `valid`.
9. Segunda validação retorna `already_used`.

## Se o backend parecer lento

A primeira chamada depois de um período sem tráfego pode acordar o serviço gratuito. Aguarde e recarregue a página; isso não indica erro da aplicação por si só.
