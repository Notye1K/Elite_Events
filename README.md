# Elite Dev — Plataforma de Eventos e Ingressos

Implementação do desafio **Elite Dev 2026**, com **Next.js + React** no frontend, **FastAPI + Python** no backend e **PostgreSQL** como banco. O fluxo foi desenhado para passar pelo cenário completo: catálogo externo → publicação → busca → escolha de assento → pagamento simulado → ingresso com QR → compartilhamento → validação de portaria.

> O desafio pede um fluxo ponta a ponta simples e completo, documentação clara e dados semeados. Os opcionais também foram implementados: busca/filtro, painel do organizador, cancelamento com devolução ao estoque, mapa de assentos em atualização em tempo real, Docker Compose, testes e preparação para deploy. fileciteturn0file0L67-L85

## Stack

- **Frontend:** Next.js 16, React 19, TypeScript, CSS próprio.
- **Backend:** FastAPI, SQLAlchemy, PyJWT.
- **Banco:** PostgreSQL 17.
- **Integração externa:** TMDb (chave opcional).
- **QR:** `qrcode.react` no cliente e token JWT assinado no backend.
- **Leitura:** `html5-qrcode`, com digitação manual como fallback.
- **Infra:** Docker Compose.
- **Testes:** pytest (ingressos, validação de eventos e regras de exclusão).

## Como rodar com Docker

1. Copie `.env.example` para `.env`.
2. Opcionalmente preencha `TMDB_API_KEY` para habilitar o catálogo externo de filmes.
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

O seed cria o evento publicado **Noite de Cinema Elite** com 40 lugares.

## Fluxo de demonstração

### Cliente

1. Entre com `cliente1@elite.dev`.
2. Acesse **Eventos**.
3. Abra o evento semeado e escolha um ou mais assentos. Cada clique alterna o lugar entre selecionado e desmarcado.
4. Clique em **Pagar simulado** para aprovar o grupo ou **Simular recusa** para testar a devolução imediata de todos os lugares ao estoque.
5. Abra **Meus ingressos** para ver o QR e o link compartilhável.
6. Abra o link em outra aba ou dispositivo para testar a visualização pública do ingresso.
7. Cancele uma compra por API se quiser demonstrar devolução ao estoque: `POST /reservations/{id}/cancel`.

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

O projeto usa o **TMDb** como catálogo externo de filmes. O endpoint `GET /external/catalog` recebe `source=tmdb` e `q=<texto>`.

Exemplo:

```bash
curl 'http://localhost:8000/external/catalog?source=tmdb&q=batman'
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
| Capacidade | 1 a 1.000 lugares |
| Preço | 0 a 10.000.000 de centavos (até R$ 100.000,00) |
| ID externo | Opcional; até 120 caracteres |

A busca no catálogo do TMDb aceita consultas de até 200 caracteres.

## Exclusão de eventos

O organizador pode excluir somente eventos criados por ele. A operação segue estas regras:

- evento futuro sem reserva ativa pode ser excluído;
- evento futuro com reserva `pending` ou `confirmed` não pode ser excluído;
- reservas canceladas ou recusadas não bloqueiam a exclusão, pois o assento já voltou ao estoque;
- evento passado pode ser excluído mesmo que tenha reservas;
- ao excluir um evento passado, ingressos, reservas e assentos relacionados também são removidos.

O endpoint protegido é `DELETE /organizer/events/{event_id}`. Tentativas de excluir eventos de outro organizador retornam `403`; eventos futuros com reservas ativas retornam `409`.

## Decisões técnicas importantes

### 1. Mapa de assentos em vez de pista por quantidade

Escolhi o mapa porque ele torna a regra de não vender o mesmo lugar duas vezes observável durante a avaliação. Também permite demonstrar o opcional de atualização em tempo real.

Na tela de compra, os lugares usam numeração visual contínua e são distribuídos em até 40 colunas, centralizadas em relação à tela/palco. Em dispositivos menores, o mapa permite rolagem horizontal para preservar a legibilidade e a área de toque de cada assento.

O cliente pode selecionar e desmarcar vários lugares antes do pagamento. A compra múltipla usa `POST /reservations/batch` e cria um ingresso individual para cada assento aprovado.

### 2. Concorrência no estoque

Cada lugar é uma linha `Seat`. Na reserva, o backend executa `SELECT ... FOR UPDATE` nos assentos, em ordem estável, e só muda `available → reserved` dentro da mesma transação. Em uma compra múltipla, todos os lugares são validados antes da primeira alteração: se um deles não estiver disponível, o lote inteiro é recusado. O estado físico dos lugares fica centralizado no banco, evitando venda dupla e compras parcialmente confirmadas.

### 3. QR não forjável

O QR não carrega apenas um ID previsível. Ele contém um JWT assinado com segredo exclusivo de ingressos, incluindo `ticket_id`, `event_id` e um `jti` aleatório. O banco guarda o hash do token e o `jti`; a portaria valida assinatura, identidade e estado persistido antes de marcar o ingresso como usado.

O `iat` do JWT é derivado da data persistida de criação do ingresso. Assim, a tela **Meus ingressos** sempre reconstrói exatamente o mesmo token e o link compartilhável continua compatível com o hash salvo no banco. Ao listar ingressos antigos, o backend corrige automaticamente hashes criados antes dessa regra.

### 4. Pagamento simulado

O desafio exige confirmação e recusa. Por isso o checkout usa dois caminhos explícitos: `approve` e `decline`. A recusa libera novamente o assento e não cria ingresso.

### 5. Compartilhamento

O link público contém o mesmo token assinado do QR. Assim não existe um segundo mecanismo de identidade do ingresso: o mesmo artefato pode ser mostrado na tela, transformado em QR ou compartilhado por URL.

### 6. Atualização em tempo real

O mapa abre um WebSocket por evento. Depois de uma reserva ou cancelamento, o backend publica `seat_updated`; clientes conectados refletem o novo estado sem precisar recarregar a página.

## Segurança e limites conscientemente assumidos

- JWT de sessão tem expiração e deve usar segredos fortes em produção.
- O QR é assinado, mas o compartilhamento de um ingresso continua sendo compartilhamento de posse; a autenticação de cliente não é usada para bloquear o link público.
- Não há recuperação de senha, e-mail, nota fiscal, revenda ou app nativo porque o próprio desafio exclui esses itens do escopo.
- O pagamento é deliberadamente simulado.
- O seed é voltado para avaliação local e deve ser removido/adaptado em produção.

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

Os testes cobrem token assinado e detecção de adulteração, validações e limites dos eventos, reservas múltiplas atômicas com pagamento aprovado ou recusado, além das regras de exclusão: evento próprio, evento de terceiros, evento passado com reserva e evento futuro com reserva ativa.

## Deploy

### Frontend — Vercel

1. Importe o diretório `frontend`.
2. Defina `NEXT_PUBLIC_API_URL` para a URL pública da API.
3. Build: `npm run build`.
4. Start: `npm start`.

### Backend — Render / Railway / Fly.io

1. Publique `backend` como serviço Python.
2. Crie um PostgreSQL gerenciado.
3. Configure `DATABASE_URL`, `JWT_SECRET`, `TICKET_SECRET`, `FRONTEND_URL`, `CORS_ORIGINS` e as chaves externas.
4. Comando de inicialização: `python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

A aplicação foi organizada para separação de responsabilidades entre frontend e API, de forma que o frontend possa estar na Vercel e o backend em outro provedor.

## Histórico e uso de IA

Consulte [`docs/AI_USAGE.md`](docs/AI_USAGE.md) para registrar o que foi acelerado por IA e quais decisões devem ser atribuídas à análise humana.

## Próximos passos que eu faria em produção

- migrar `create_all` para Alembic;
- adicionar rate limiting no login e na portaria;
- auditar ações de portaria;
- tornar chaves e secrets obrigatórios fora do ambiente local;
- criar testes de integração concorrente no Postgres real;
- adicionar observabilidade e logs estruturados;
- adicionar pipeline CI para lint, testes e build.

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

### 1. Banco PostgreSQL no Supabase

Crie um projeto gratuito no Supabase e copie a conexão PostgreSQL. Para o SQLAlchemy/psycopg, use o formato:

```text
postgresql+psycopg://USUARIO:SENHA@HOST:5432/postgres?sslmode=require
```

Se o painel fornecer uma URL `postgresql://`, adapte o prefixo para `postgresql+psycopg://` antes de colocar em `DATABASE_URL`.

> O projeto cria as tabelas automaticamente no primeiro boot. Para um projeto real eu usaria Alembic; para este desafio, o objetivo é reduzir o atrito de avaliação.

### 2. Backend no Render

Há um `render.yaml` na raiz que pode ser usado como referência/Blueprint.

Configuração manual equivalente:

- **Type:** Web Service
- **Runtime:** Docker
- **Root Directory:** `backend`
- **Plan:** Free
- **Health Check:** `/health`

Variáveis obrigatórias:

```text
DATABASE_URL=postgresql+psycopg://...
JWT_SECRET=<segredo longo e aleatório>
TICKET_SECRET=<outro segredo longo e aleatório>
FRONTEND_URL=https://SEU-PROJETO.vercel.app
CORS_ORIGINS=https://SEU-PROJETO.vercel.app
```

Variáveis opcionais:

```text
TMDB_API_KEY=...
```

O Dockerfile do backend respeita automaticamente a variável `$PORT` fornecida pelo Render.

Teste após o deploy:

```text
https://SEU-BACKEND.onrender.com/health
```

Deve responder:

```json
{"status":"ok"}
```

O seed é idempotente e roda no boot, portanto os quatro usuários de avaliação e o evento de demonstração são criados sem exigir uma etapa manual de migração/seed.

### 3. Frontend na Vercel

Crie um projeto na Vercel apontando para o mesmo repositório GitHub.

No projeto da Vercel:

- **Root Directory:** `frontend`
- Framework detectado: **Next.js**
- Build: `npm run build`
- Start: `npm start`
- Variável de ambiente:

```text
NEXT_PUBLIC_API_URL=https://SEU-BACKEND.onrender.com
```

O arquivo `frontend/vercel.json` deixa explícito que o diretório é um projeto Next.js.

Depois de obter a URL da Vercel, volte ao Render e configure:

```text
FRONTEND_URL=https://SEU-PROJETO.vercel.app
CORS_ORIGINS=https://SEU-PROJETO.vercel.app
```

Isso é necessário porque o backend usa `FRONTEND_URL` para gerar links compartilháveis dos ingressos e `CORS_ORIGINS` para aceitar as chamadas do navegador.

### 4. WebSocket em produção

O mapa de assentos usa:

```text
/ws/events/{event_id}/seats
```

O frontend converte automaticamente `http://` em `ws://` e `https://` em `wss://`. Assim, no deploy HTTPS, a conexão passa a ser segura sem nenhuma configuração manual adicional no frontend.

O Render mantém a conexão WebSocket do serviço FastAPI; o banco continua sendo a fonte de verdade para o status dos assentos.

### 5. Checklist de deploy

- [ ] Criar repositório público no GitHub.
- [ ] Fazer push de todo o monorepo.
- [ ] Criar PostgreSQL no Supabase.
- [ ] Criar API no Render com `backend` como Root Directory.
- [ ] Configurar `DATABASE_URL`, `JWT_SECRET`, `TICKET_SECRET`.
- [ ] Criar frontend na Vercel com `frontend` como Root Directory.
- [ ] Configurar `NEXT_PUBLIC_API_URL`.
- [ ] Copiar a URL da Vercel para `FRONTEND_URL` e `CORS_ORIGINS` no Render.
- [ ] Abrir `/health` do backend.
- [ ] Fazer login com `cliente1@elite.dev` / `123456`.
- [ ] Comprar um assento.
- [ ] Confirmar QR em **Meus ingressos**.
- [ ] Abrir a URL compartilhável.
- [ ] Entrar como `portaria@elite.dev` / `123456` e validar o QR.
- [ ] Validar novamente para demonstrar `already_used`.

### 6. Limitações do free tier que devem ser conhecidas

O backend gratuito pode dormir quando fica sem tráfego e demorar alguns segundos para acordar na primeira requisição. Isso é aceitável para o cenário de avaliação, mas deve ser mencionado ao avaliador caso ele abra o projeto após um período sem acesso.

O banco gratuito também tem limites de armazenamento/uso. O desafio é pequeno e o seed contém apenas um evento e poucos usuários, portanto a carga esperada é baixa.

### 7. Alternativa: tudo no Render

Também é possível hospedar o frontend como Web Service Node no Render e manter o backend no Render. Ainda assim, para este desafio eu prefiro **Vercel + Render + Supabase**, porque o Next.js fica no ambiente mais natural para ele, a API fica isolada e o PostgreSQL não depende do banco efêmero/free de um PaaS.
