# Arquitetura

```text
Next.js
  ├─ /events                descoberta + filtros
  ├─ /events/[id]           mapa de filme ou contador de show + checkout
  ├─ /tickets               QR + compartilhamento
  ├─ /organizer             catálogo + publicação
  └─ /gate                  câmera/manual + validação
          │ HTTP / WS
          ▼
FastAPI
  ├─ Auth / RBAC
  ├─ Eventos / Seats
  ├─ Checkout Stripe / Reservas / Cancelamento
  ├─ Tickets / Share
  ├─ Gate validation
  └─ External catalog adapters
          │
          ▼
PostgreSQL
```

## Entidades

- `users`: identidade + papel.
- `events`: publicação e metadados editoriais.
- `seats`: inventário de cadeiras de filme ou unidades gerais de show; unidades de show não são expostas como assentos.
- `reservations`: intenção/estado de compra.
- `payment_checkouts`: sessão de compra, valor calculado no backend, expiração e IDs da Stripe.
- `checkout_reservations`: associação entre uma sessão de pagamento e suas reservas.
- `tickets`: ingresso final, estado de uso e material criptográfico associado.

## Invariantes

1. `Seat.status = reserved` só acontece em uma transação que passou por lock do registro.
2. Reserva recusada não gera ticket.
3. Ticket só existe para reserva confirmada.
4. Ticket usado não pode ser usado de novo.
5. Ticket de outro evento nunca é aceito na portaria.
6. Token com assinatura inválida ou hash incompatível não é aceito.
7. Cancelar reserva devolve a unidade de estoque para `available` e invalida o ticket.
8. Ticket só é criado depois que a Stripe confirma `payment_status=paid`; webhooks repetidos são idempotentes.
9. Checkouts pendentes, cancelados ou expirados não geram tickets e liberam o estoque.
10. Filmes têm 200 cadeiras em fileiras de 20; shows exigem capacidade e não permitem escolha de assento.

## Deployment topology

The repository is intentionally deployable as two independent applications:

- `frontend/` is a Next.js application suitable for Vercel.
- `backend/` is a Dockerized FastAPI service suitable for Render.
- PostgreSQL is externalized so production/demo deployments can use Supabase.

This preserves the local Docker Compose experience while avoiding a single-host deployment as a prerequisite for the public demo.

The backend Docker image consumes `$PORT`, so it is compatible with PaaS platforms that inject the listening port at runtime. CORS and share-link generation are configured through `CORS_ORIGINS` and `FRONTEND_URL` respectively.
