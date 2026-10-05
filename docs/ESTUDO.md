# Etapa 1

## O que mudou


## Por que


## Como testar


### Perguntas de entrevista

- Por que salvar a resposta da IA antes de tentar interpretar o JSON?
- Como o hash do arquivo ajuda a rastrear uma extração?
- O que acontece se o banco falhar ao salvar a resposta bruta?

# Etapa 2

## O que mudou


## Por que


## Como testar


### Perguntas de entrevista

- Por que CNPJs com pontuação podem representar o mesmo identificador?
- Por que a normalização não removeria zeros à esquerda do número da nota?
- Como um insert direto pelo n8n contorna uma normalização feita só no FastAPI?

# Etapa 3

## O que mudou


## Por que


## Como testar


### Perguntas de entrevista

- O que acontece se dois pedidos tentarem inserir a mesma nota ao mesmo tempo?
- Por que `ON CONFLICT DO NOTHING` pode fazer o insert não retornar um id?
- Como testar concorrência usando duas conexões independentes?

# Etapa 4

## O que mudou


## Por que


## Como testar


### Perguntas de entrevista

- Como você explicaria cada etapa deste pipeline em uma entrevista?
- Que evidência diferencia um teste com mock de um teste com PostgreSQL real?
- Como separar uma falha de extração de uma falha de gravação?

## Testes manuais no n8n

1. Reimporte `n8n/workflow.json`.
2. Envie uma nota válida.
3. Envie uma nota inválida.
4. Envie a mesma nota válida duas vezes.
5. Envie 12 notas rapidamente para provocar HTTP 429.
6. Confirme que erro de API, inclusive 429, não cria uma linha rejeitada falsa.

Não consigo executar o n8n; esses passos precisam ser validados manualmente.
