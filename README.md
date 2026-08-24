# Elite Dev — Plataforma de Eventos e Ingressos

Implementação do desafio **Elite Dev 2026**, com **Next.js + React** no frontend, **FastAPI + Python** no backend e **PostgreSQL** como banco. O fluxo foi desenhado para passar pelo cenário completo: catálogo externo → publicação → busca → escolha de assento ou quantidade → Checkout Stripe em sandbox → ingresso com QR → compartilhamento → validação de portaria.

> O desafio pede um fluxo ponta a ponta simples e completo, documentação clara e dados semeados. Os opcionais também foram implementados: busca, painel do organizador, cancelamento com devolução ao estoque, mapa de assentos em atualização em tempo real, Docker Compose, testes e preparação para deploy.

**Demonstração publicada:** [https://frontend-iota-ashy-55.vercel.app/](https://frontend-iota-ashy-55.vercel.app/)

## Stack

- **Frontend:** Next.js 16, React 19, TypeScript, CSS próprio.
- **Backend:** FastAPI, SQLAlchemy, PyJWT.
- **Banco:** PostgreSQL 17.
- **Integrações externas:** TMDb para filmes, Ticketmaster Discovery API para shows e Stripe Checkout para pagamentos em ambiente de teste.
- **QR:** `qrcode.react` no cliente e token JWT assinado no backend.
- **Leitura:** `html5-qrcode`, com digitação manual como fallback.
- **Infra:** Docker Compose.
- **Testes:** pytest (ingressos, validação de eventos e regras de exclusão).

## Como rodar com Docker

1. Copie `.env.example` para `.env`.
2. Opcionalmente preencha `TMDB_API_KEY` para filmes e `TICKETMASTER_API_KEY` para shows. Para testar compras, preencha `STRIPE_SECRET_KEY` com uma chave de sandbox/teste e `STRIPE_WEBHOOK_SECRET` com o segredo do webhook.
3. Rode:

```bash
docker compose up --build
```

ou para o modo dev

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Acesse:

- Frontend: http://localhost:3000
- API / Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health

O container do backend cria as tabelas e executa o seed antes de subir a API.

### Dados de avaliação

Todos usam senha `123456`:

| Papel | Email |
|---|---|
| Organizador | `organizador@elite.dev` |
| Cliente 1 | `cliente1@elite.dev` |
| Cliente 2 | `cliente2@elite.dev` |
| Portaria | `portaria@elite.dev` |

Em um banco novo, o seed cria o evento publicado **Noite de Cinema Elite** com 200 lugares, distribuídos em fileiras de 20.

## Fluxo de demonstração

### Cliente

1. Entre com `cliente1@elite.dev`.
2. Acesse **Eventos**.
3. Em um filme, escolha um ou mais assentos; em um show, escolha a quantidade no estoque geral.
4. Clique em **Continuar para pagamento**, revise a compra e abra o Checkout da Stripe.
5. No sandbox, use `4242 4242 4242 4242` para aprovação, `4000 0000 0000 0002` para recusa genérica ou `4000 0000 0000 9995` para saldo insuficiente. Use qualquer data futura e CVC de três dígitos.
6. Após a confirmação, abra **Meus ingressos** para ver o QR, copiar o código usado na portaria ou abrir o link compartilhável.
7. Abra o link em outra aba ou dispositivo para testar a visualização pública do ingresso.
8. Em **Meus ingressos**, cancele um ingresso válido para demonstrar o reembolso no sandbox e a devolução do estoque.

### Stripe local com Docker

O frontend usa o Checkout hospedado; portanto, a chave pública da Stripe não é necessária. A chave secreta nunca é enviada ao navegador.

Para receber webhooks enquanto o backend roda no Docker:

```bash
stripe login
stripe listen --forward-to localhost:8000/payments/stripe/webhook
```

Copie o segredo `whsec_...` exibido pela Stripe CLI para `STRIPE_WEBHOOK_SECRET` no `.env`. Como as variáveis são injetadas pelo Compose na criação do container, recrie o backend depois de alterar o `.env`:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build --force-recreate backend
```

Se a criação do pagamento falhar, acompanhe o backend em outro terminal:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f backend
```

O frontend recebe uma mensagem segura e o backend registra o traceback com o identificador do checkout, evento e tipo da exceção da Stripe. As chaves não são incluídas nessas mensagens pela aplicação.

### Portaria

1. Entre com `portaria@elite.dev`.
2. Acesse **Portaria**.
3. Use a câmera para ler o QR ou cole o conteúdo do QR no campo manual.
4. O retorno pode ser:
   - `valid` — entrada autorizada;
   - `invalid` — código adulterado, inexistente ou cancelado;
   - `already_used` — tentativa de reutilização;
   - `event_wrong` — ingresso pertence a outro evento.

## Catálogo externo

O projeto usa o **TMDb** como catálogo externo de filmes e a [Ticketmaster Discovery API v2](https://developer.ticketmaster.com/products-and-docs/apis/discovery-manual/v2/) como catálogo de shows. O endpoint `GET /external/catalog` recebe `source=tmdb|ticketmaster` e `q=<texto>`. A busca da Ticketmaster filtra a classificação `music` e usa a Consumer Key no parâmetro `apikey`, somente no backend.

Exemplo:

```bash
curl 'http://localhost:8000/external/catalog?source=tmdb&q=batman'
curl 'http://localhost:8000/external/catalog?source=ticketmaster&q=coldplay'
```

Sem chave configurada, o endpoint retorna `configured=false`; o restante do sistema continua funcionando com o catálogo local/seed.

## Limites para criação de eventos

Os limites são validados no formulário e novamente pela API. Título, descrição, data/hora, local, capacidade e preço são obrigatórios; imagem e ID externo são opcionais.

| Campo | Limite |
|---|---|
| Título | 1 a 255 caracteres; não aceita somente espaços |
| Descrição | 1 a 5.000 caracteres; não aceita somente espaços |
| Imagem (URL) | Opcional; URL HTTP/HTTPS com até 500 caracteres |
| Data/hora | No mínimo 24 horas de antecedência e no máximo 10 anos no futuro |
| Local | 1 a 255 caracteres; não aceita somente espaços |
| Tipo | `movie` (filme) ou `show` |
| Capacidade | Filme: fixa em 200 cadeiras, 20 por fileira. Show: obrigatória, de 1 a 1.000 ingressos gerais |
| Preço | 0 a 10.000.000 de centavos (até R$ 100.000,00) |
| ID externo | Opcional; até 120 caracteres |

As buscas nos catálogos do TMDb e da Ticketmaster aceitam consultas de até 200 caracteres. Quando há ID externo, a API também garante que TMDb seja usado apenas em filmes e Ticketmaster apenas em shows.

## Autorização por role

A API é a autoridade de segurança e valida o token e a role em todos os endpoints protegidos. O frontend também aplica guards nas páginas privadas e mostra no header apenas a opção pertinente ao usuário autenticado.

| Área ou ação | Acesso |
|---|---|
| Lista, detalhes, assentos e disponibilidade | Público, inclusive sem login |
| Selecionar assentos ou quantidade e comprar ingressos | Somente `client` |
| Meus ingressos | Somente `client` |
| Painel e ações do organizador | Somente `organizer` |
| Portaria e validação de ingresso | Somente `gate` |
| Link de ingresso compartilhado | Público, mediante token assinado válido |

Visitantes que tentarem abrir uma página privada são enviados ao login. Usuários autenticados com uma role diferente são enviados à página pública de eventos.

O cadastro permite escolher livremente entre cliente, organizador e portaria. Isso foi mantido de propósito para que qualquer avaliador consiga criar e testar todos os tipos de usuário sem depender de uma conta administrativa. Em produção, organizadores e profissionais de portaria normalmente seriam convidados ou aprovados por um administrador.

## Cancelamento de ingressos

Na página **Meus ingressos**, o cliente pode cancelar um ingresso próprio enquanto ele estiver com status `valid`. O cancelamento usa `POST /tickets/{ticket_id}/cancel` e executa na mesma transação:

- ingresso `valid → cancelled`;
- reserva `confirmed → cancelled`;
- pagamento `paid → refunded`;
- unidade de estoque `reserved → available` (cadeira no filme ou ingresso geral no show).

Ingressos de outro cliente, já utilizados ou já cancelados não podem ser cancelados. O backend valida a propriedade e o estado do ingresso mesmo que o endpoint seja chamado diretamente.

## Exclusão de eventos

O organizador pode excluir somente eventos criados por ele. A operação segue estas regras:

- evento futuro sem reserva ativa pode ser excluído;
- evento futuro com reserva `pending` ou `confirmed` não pode ser excluído;
- reservas canceladas ou recusadas não bloqueiam a exclusão, pois o assento já voltou ao estoque;
- evento passado pode ser excluído mesmo que tenha reservas;
- ao excluir um evento passado, ingressos, reservas e assentos relacionados também são removidos.

O endpoint protegido é `DELETE /organizer/events/{event_id}`. Tentativas de excluir eventos de outro organizador retornam `403`; eventos futuros com reservas ativas retornam `409`.

## Decisões técnicas importantes

### 1. Dois tipos de inventário

Filmes usam capacidade fixa de 200 cadeiras em 10 fileiras de 20. O mapa torna a regra de não vender o mesmo lugar duas vezes observável durante a avaliação.

Shows não expõem assentos: a tela mostra um contador de ingressos disponíveis e uma seleção de quantidade. Internamente, cada ingresso geral ainda é uma unidade de estoque bloqueável, permitindo reutilizar as garantias de concorrência, cancelamento, exclusão e WebSocket sem criar uma segunda arquitetura de reservas.

Filmes e shows iniciam a compra exclusivamente por `POST /checkout/sessions`, usando o mesmo fluxo de reserva temporária e confirmação de pagamento.

### 2. Concorrência no estoque

Cada cadeira ou ingresso geral é uma linha `Seat`. Na reserva, o backend executa `SELECT ... FOR UPDATE` em ordem estável e só muda `available → reserved` dentro da mesma transação. Shows usam `SKIP LOCKED` na escolha automática do estoque. Todas as unidades são validadas antes da primeira alteração: se não houver quantidade suficiente, o lote inteiro é recusado.

### 3. QR não forjável

O QR não carrega apenas um ID previsível. Ele contém um JWT assinado com segredo exclusivo de ingressos, incluindo `ticket_id`, `event_id` e um `jti` aleatório. O banco guarda o hash do token e o `jti`; a portaria valida assinatura, identidade e estado persistido antes de marcar o ingresso como usado.

O `iat` do JWT é derivado da data persistida de criação do ingresso. Assim, a tela **Meus ingressos** sempre reconstrói exatamente o mesmo token e o link compartilhável continua compatível com o hash salvo no banco. Ao listar ingressos antigos, o backend corrige automaticamente hashes criados antes dessa regra.

### 4. Checkout Stripe e reserva temporária

Ao criar um checkout, o backend bloqueia as unidades de estoque com `SELECT ... FOR UPDATE`, cria reservas `pending` e uma linha em `payment_checkouts`. O Checkout hospedado pela Stripe recebe o preço calculado exclusivamente no backend; o navegador nunca informa o valor cobrado.

A sessão expira em cerca de 30 minutos, que é o mínimo aceito pela Stripe. Enquanto estiver aberta, os assentos ou ingressos gerais ficam indisponíveis para outros clientes. O fluxo de estados é:

- `pending` — estoque temporariamente reservado e Checkout aberto;
- `processing` — método assíncrono concluído no Checkout, mas ainda sem confirmação financeira;
- `paid` — webhook ou sincronização autenticada confirmou o pagamento e criou um ingresso por reserva;
- `failed`, `cancelled` ou `expired` — nenhuma entrada é criada e o estoque volta a `available`;
- `partially_refunded` ou `refunded` — um ou todos os ingressos da compra foram cancelados.

O endpoint `POST /payments/stripe/webhook` valida o corpo original com `Stripe-Signature` e `STRIPE_WEBHOOK_SECRET`. A confirmação é idempotente: reenvios do mesmo evento não duplicam ingressos. A página de retorno também consulta a sessão diretamente na Stripe para tolerar atraso na entrega do webhook, mas nunca confia apenas nos parâmetros da URL.

Eventos com preço zero são confirmados internamente sem criar uma cobrança Stripe. O cancelamento de um ingresso pago solicita um reembolso parcial do valor daquele ingresso usando uma chave de idempotência; o estoque só é devolvido se a Stripe aceitar o reembolso.

### 5. Compartilhamento

O link público contém o mesmo token assinado do QR. Assim não existe um segundo mecanismo de identidade do ingresso: o mesmo artefato pode ser mostrado na tela, transformado em QR ou compartilhado por URL.

### 6. Atualização em tempo real

A tela de compra abre um WebSocket por evento. Depois de uma reserva ou cancelamento, o backend publica `seat_updated` com a disponibilidade atual; mapas de filmes e contadores de shows refletem o novo estoque sem recarregar a página.

### 7. Janela de validação na portaria

Considerei permitir que a portaria validasse o ingresso somente no horário exato do evento, mas optei por uma regra menos rígida para não tornar a aplicação e o fluxo de demonstração pouco práticos. Reservas e validações na portaria são bloqueadas para eventos de dias anteriores; eventos do dia atual continuam liberados mesmo que o horário de início já tenha passado, e eventos futuros também permanecem liberados.

A comparação usa o dia civil no fuso `America/Sao_Paulo`, configurável por `APP_TIMEZONE`. O backend aplica a regra como fonte de verdade: uma tentativa de reserva para data anterior retorna `409`, e a portaria responde como ingresso inválido sem marcar o ingresso como utilizado. A tela de assentos também desabilita antecipadamente a seleção nesses eventos.

Em uma aplicação de produção, essa regra poderia ser retomada como uma janela configurável pelo organizador, por exemplo permitindo a entrada algumas horas antes do início e encerrando a validação após o término do evento.

## Segurança e limites conscientemente assumidos

- JWT de sessão tem expiração e deve usar segredos fortes em produção.
- O cadastro aberto de organizador e portaria é uma decisão consciente para facilitar a avaliação de todas as roles; em produção esses papéis exigiriam convite ou aprovação administrativa.
- O QR é assinado, mas o compartilhamento de um ingresso continua sendo compartilhamento de posse; a autenticação de cliente não é usada para bloquear o link público.
- Não há recuperação de senha, e-mail, nota fiscal, revenda ou app nativo porque o próprio desafio exclui esses itens do escopo.
- A Stripe está integrada em sandbox para a demonstração. Com `STRIPE_TEST_MODE=true`, o backend recusa chaves que não comecem com `sk_test_` ou `rk_test_`, evitando cobranças acidentais. Passar para produção exige alterar conscientemente essa opção, usar chaves de produção, HTTPS, revisar os meios de pagamento e configurar outro webhook; este projeto não ativa cobranças reais por padrão.
- O seed é voltado para avaliação local e deve ser removido/adaptado em produção.

### Decisões de escopo do organizador

A interface do organizador não possui edição de eventos de propósito. Uma edição segura teria de bloquear mudanças relevantes depois da emissão de ingressos; como o formulário tem poucos campos e a maioria é preenchida automaticamente ao selecionar um filme ou show, preferi não adicionar essa feature ao desafio.

Também considerei um sistema de cancelamento do evento que notificaria os clientes com ingressos emitidos. A ideia surgiu no último dia, e preferi não introduzir um fluxo novo perto da entrega sem saber se alterações adicionais seriam permitidas depois do prazo e antes da avaliação. A exclusão existente continua deliberadamente limitada pelas regras documentadas acima.

## Testes

Com o ambiente Docker de desenvolvimento:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm backend python -m pytest -q
```

Ou com Python 3.12 e dependências instaladas:

```bash
cd backend
pytest -q
```

Os testes cobrem token assinado e adulteração, limites dos eventos, adaptadores TMDb e Ticketmaster, mapa de 200 cadeiras, estoque geral de shows, compras atômicas, concorrência real no PostgreSQL, esgotamento, cancelamento, RBAC, datas, portaria, exclusão de eventos e o Checkout Stripe: bloqueio temporário, aprovação, falha, cancelamento, propriedade e idempotência do webhook.

## CI/CD

O workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) roda em pushes e pull requests para `main`. Ele executa:

- `npm ci`, lint e build de produção do frontend;
- testes do backend com Python 3.12 e PostgreSQL 17, incluindo o cenário concorrente de validação na portaria;
- validação da combinação dos arquivos Docker Compose.

O CD não é duplicado no GitHub Actions: Vercel e Render já observam o repositório e publicam automaticamente depois de um push na branch conectada (`autoDeploy: true` no `render.yaml`). O fluxo recomendado é **pull request → CI aprovado → merge em `main` → deploy automático nas plataformas**. Para impedir que uma falha chegue a produção, a branch `main` deve ser protegida exigindo o sucesso do CI antes do merge; um push direto em `main` pode iniciar o deploy externo antes de o workflow terminar.

## Deploy

### Frontend — Vercel

URL publicada: [https://frontend-iota-ashy-55.vercel.app/](https://frontend-iota-ashy-55.vercel.app/)

### Backend — Render / Railway / Fly.io

A aplicação foi organizada para separação de responsabilidades entre frontend e API, de forma que o frontend possa estar na Vercel e o backend em outro provedor.

## Histórico e uso de IA

Consulte [`docs/AI_USAGE.md`](docs/AI_USAGE.md) para registrar o que foi acelerado por IA e quais decisões devem ser atribuídas à análise humana. O arquivo [`AGENTS.md`](AGENTS.md) também foi incluído como artefato de contexto usado durante o desenvolvimento assistido.

## Próximos passos que eu faria em produção

- migrar `create_all` para Alembic;
- adicionar rate limiting no login e na portaria;
- auditar ações de portaria;
- adicionar gerenciamento administrativo e convites para roles privilegiadas;
- adicionar observabilidade e logs estruturados;
- implementar edição e cancelamento de eventos com regras de imutabilidade, reembolso e notificação dos clientes.

## Deploy gratuito recomendado (produção de avaliação)

Para uma entrega pública simples, o monorepo foi preparado para separar o frontend e a API:

```text
GitHub
├── frontend/  → Vercel (Next.js)
└── backend/   → Render Free (FastAPI + Docker)
                     │
                     └── Supabase Free (PostgreSQL)
```

O `docker-compose.yml` continua sendo o caminho recomendado para avaliação local. O deploy público usa os mesmos diretórios e não depende de manter um único servidor para todo o monorepo.

### 1. Limitações do free tier que devem ser conhecidas

O backend gratuito pode dormir quando fica sem tráfego e demorar alguns segundos para acordar na primeira requisição. Isso é aceitável para o cenário de avaliação, mas deve ser mencionado ao avaliador caso ele abra o projeto após um período sem acesso.

O banco gratuito também tem limites de armazenamento/uso. O desafio é pequeno e o seed contém apenas um evento e poucos usuários, portanto a carga esperada é baixa.
