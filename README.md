# NF Pipeline Automation

Pipeline de automação para processamento de notas fiscais: recebimento, extração de dados via IA, validação de regras de negócio e persistência em banco — com roteamento automático entre notas aprovadas e rejeitadas.

## Arquitetura

O **n8n** orquestra o fluxo do início ao fim. O serviço em **Python (FastAPI)** entra como microsserviço de apoio, chamado via HTTP, responsável por duas coisas isoladas de propósito:

- **Extração** (`/extract`): usa a API do Gemini para ler o documento e extrair os campos da nota
- **Validação** (`/validate`): aplica regras de negócio puras (CNPJ, valor, data, duplicidade) — sem depender de IA

Separar extração de validação foi uma decisão deliberada: o provedor de IA pode mudar ou falhar, mas a lógica de negócio não deve depender disso.

```
Webhook → Extrair Dados (IA) → HTTP Request → Validar Regras de Negócio → IF (nota válida?)
                                                                              ├─ true  → Postgres: grava nota aprovada
                                                                              └─ false → Postgres: grava nota rejeitada (com motivo)
                                                                                              ↓
                                                                                    Responde Webhook
```

Cada nota rejeitada é gravada no banco (não apenas notificada por e-mail), com:
- valores de fallback nas colunas obrigatórias quando a IA não consegue extrair um campo (nota inválida/ilegível)
- `numero_nota` único por execução, evitando colisão de constraint quando múltiplas notas inválidas caem no mesmo fallback
- `motivo_rejeicao` preenchido com a razão da rejeição

## Stack

- **n8n** — orquestração do fluxo
- **Python / FastAPI** — extração (Gemini) e validação de regras de negócio
- **PostgreSQL** — persistência de notas aprovadas e rejeitadas
- **Docker Compose** — sobe os 3 serviços (n8n, Postgres, extraction_service) de uma vez

## Estrutura

```
nf-pipeline-automation/
├── docker-compose.yml
├── .env.example
├── db/
│   └── init.sql                # cria as tabelas automaticamente
├── extraction_service/
│   ├── main.py                 # extração (IA) + validação de regras
│   ├── requirements.txt
│   └── Dockerfile
└── n8n/
    └── workflow.json           # fluxo completo pronto pra importar
```

## Como rodar

1. Gere uma chave gratuita da API do Gemini em https://aistudio.google.com/app/apikey
2. Copie `.env.example` para `.env` e cole a chave
3. Suba os containers:
   ```bash
   docker compose up -d --build
   ```
4. Acesse `http://localhost:5678`, importe `n8n/workflow.json` e configure a credencial do Postgres (host `postgres`, database `nf_pipeline`, user `nf_user`)
5. Publique o workflow e teste:
   ```bash
   curl -X POST http://localhost:5678/webhook/nota-fiscal -F "data=@caminho/para/nota.png"
   ```
6. Confira o resultado direto no banco:
   ```bash
   docker compose exec postgres psql -U nf_user -d nf_pipeline -c "SELECT * FROM notas_fiscais ORDER BY id DESC;"
   ```

Também é possível testar a extração e validação isoladamente, sem o n8n:
```bash
curl -X POST http://localhost:8000/process -F "file=@caminho/para/nota.png"
```

## Regras de negócio implementadas

Em `extraction_service/main.py`, função `validar_dados`:

- CNPJ inválido — validação real dos dígitos verificadores, não só formato (`cnpj_e_valido`)
- Valor zero ou negativo
- Data de emissão no futuro
- Nota duplicada — consulta ao Postgres (`nota_ja_existe`)

## Testado

Fluxo validado ponta a ponta com nota fiscal válida (caminho aprovada) e com documento inválido (caminho rejeitada), incluindo tratamento de valores nulos e constraint de unicidade no banco.

## Próximos passos

- Endpoint de consulta de status por número de nota
- Dashboard (Grafana) com métricas de aprovação/rejeição
- Testes automatizados para `validar_dados`
