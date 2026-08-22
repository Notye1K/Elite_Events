# Uso de IA

Este projeto foi produzido com apoio de IA, em vez de esconder esse fato. O objetivo deste documento é separar **aceleração de implementação** de **decisões de produto/arquitetura**.

## Uso de IA

- geração inicial de boilerplate de Next.js/FastAPI;
- criação de schemas, modelos e endpoints repetitivos;
- apoio na documentação e nos exemplos de execução;
- revisão de casos de erro do fluxo de portaria;
- criação de testes unitários básicos;
- revisão da estrutura do Compose.

## Decisões que precisam permanecer explicitamente humanas

- escolher mapa de assentos em vez de pista;
- escolher PostgreSQL e uma linha `Seat` como fonte de verdade do estoque;
- tratar pagamento recusado como operação que libera estoque imediatamente;
- usar JWT assinado com `jti` + hash persistido para o QR;
- separar os papéis de organizador, cliente e portaria;
- usar WebSocket para refletir a mudança do assento sem polling agressivo;
- manter o catálogo externo como fonte de descoberta, não como fonte de verdade do evento publicado.

## Como melhorar este registro no GitHub

Ao trabalhar no desafio, faça commits pequenos e descritivos, por exemplo:

- `feat: scaffold next and fastapi apps`
- `feat: add event catalog integration`
- `feat: implement seat reservation transaction`
- `feat: add signed ticket qr`
- `feat: add gate validation and replay protection`
- `feat: add realtime seat updates`
- `test: cover ticket integrity rules`
- `docs: explain architecture and ai usage`

O histórico é parte da narrativa do projeto, porque o desafio explicitamente pede commits ao longo da semana. fileciteturn0file0L87-L102
