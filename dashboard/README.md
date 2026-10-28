# Painel de custos da obra

Painel em React + Vite, nesta pasta separada do projeto, que consulta `GET /obras/{id}/resumo`. Ele não altera o back-end, o Docker, o n8n nem a interface de upload existente.

## Modos de dados

- **Real:** consulta a API local usando o campo de chave da API e o ID da obra.
- **Demo:** usa dados fixos de `src/dadosDemo.js` e é ativado automaticamente no build de produção. A obra e os valores são simulados.

O painel apresenta orçamento total, gasto total, percentual gasto, etapas em alerta e as nove etapas com barras de progresso limitadas a 100% e marca em 90%. O alerta é indicado a partir de 90%. Também mostra a linha “Sem classificação”, estado de carregamento e erros de chave inválida, obra não encontrada e API fora do ar, com botão “Tentar de novo”.

## Como executar

Ligue o Docker do NF. Nesta pasta, execute:

```sh
npm install
npm run dev
```

Abra `http://localhost:5173`. Durante `npm run dev`, o proxy do Vite em `vite.config.js` encaminha `/obras` para `http://localhost:8000`; assim, não é necessário alterar CORS no back-end. O proxy só existe no servidor de desenvolvimento.

## Segurança e limitações

A chave é digitada na tela e fica somente em memória enquanto a aba estiver aberta; não a coloque no código nem em arquivo versionado. No build publicado não há proxy, então a aplicação inicia em modo Demo. O percentual retornado pela API é uma fração (`0.0717` = `7,17%`). Não há edição de dados pela interface.

## Status de validação

| Estado | Verificação |
|---|---|
| **PROVADO** | `npm run build` e `npm run lint` concluídos sem erros. |
| **PROVADO** | Modo Demo conferido visualmente no navegador: totais, nove etapas, alerta na Hidráulica e linha “Sem classificação”. |
| **NÃO PROVADO** | Modo Real com chave válida contra a API; mensagens de chave inválida, obra não encontrada e API desligada; layout no celular. |

Prints: a adicionar
