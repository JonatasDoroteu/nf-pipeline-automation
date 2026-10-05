1. O webhook recebe o documento e o fluxo chama `POST /extract-base64` para extração e `POST /validate` para validação; não chama `/process`.
2. `Postgres - Grava Nota Aprovada` insere em `notas_fiscais` as colunas `numero_nota,cnpj_emitente,valor_total,data_emissao,status`; o JSON configura `operation=insert` e não contém SQL literal.
3. `Postgres - Grava Nota Rejeitada` insere em `notas_fiscais` as colunas `numero_nota,cnpj_emitente,valor_total,data_emissao,status,motivo_rejeicao,dados_brutos_extraidos`; o JSON não contém SQL literal.
4. Nenhum nó chama `/notas-rejeitadas`; esse endpoint também não está definido em `extraction_service/main.py`.
5. Os testes existentes não usam banco real: os testes da API substituem a checagem de duplicidade com monkeypatch e os testes de avaliação comparam dados em memória.
6. A Etapa 2 foi pulada: normalizar apenas no FastAPI não alcançaria os inserts feitos diretamente pelos dois nós Postgres do n8n.
7. Mesmo com `/validate` chamado pelo n8n, o insert posterior é feito pelo próprio workflow e não passa por `gravar_nota_fiscal`.
8. Migração 001 e concorrência real: NÃO VALIDADO; Docker Compose não iniciou e `DATABASE_URL` não estava definida. A Etapa 3 foi revertida. Baseline: 24 testes passaram no diretório `extraction_service`; na raiz a coleta falha porque `frontend` é relativo.
