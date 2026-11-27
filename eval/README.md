# Avaliação de extração

## Executar

No PowerShell, a partir de `extraction_service`:

```powershell
python ..\eval\run_eval.py --runs 3
```

O arquivo `.env` na raiz do repositório deve definir `GEMINI_API_KEY` e `GEMINI_MODEL`. O runner carrega esse arquivo sem sobrescrever variáveis já presentes no ambiente da sessão; portanto, se `GEMINI_API_KEY` já estiver definida na sessão, esse valor será usado no lugar do valor do `.env`.

O eval chama diretamente a função de extração de produção, sem fazer uma requisição HTTP ao FastAPI. Após a extração, a produção tenta gravar a resposta bruta no PostgreSQL. Se não houver banco local, o erro é registrado no log e ignorado; isso não afeta o resultado da extração.

Opções:

- `--runs`: execuções por nota (padrão `3`).
- `--sleep`: pausa, em segundos, entre chamadas (padrão `0`).
- `--max-tentativas`: máximo de tentativas do eval para erros 429 (padrão `3`).
- `--resume <arquivo.json>`: reutiliza extrações bem-sucedidas do relatório indicado, recalculando as comparações com os gabaritos atuais. Falhas e runs ausentes são executados novamente. Aborta se o modelo for diferente ou não estiver registrado. Nunca altera o relatório de origem e grava um relatório novo.

O retry de 429 existe somente no eval, não na produção. O retry interno de 503 da produção não é contado pelo eval.

## Testes

A partir da raiz do repositório:

```powershell
python -m pytest -q eval\tests\test_run_eval.py
```

Esses testes usam dados e erros falsos: não chamam o Gemini nem acessam a rede. Não são coletados pelo CI, que executa `pytest -q` a partir de `extraction_service`.

## Ler o relatório

Os relatórios novos ficam em `eval/resultados/`. `resumo` contém:

- Acerto por campo e acerto total, calculados somente nas execuções com saída válida.
- `execucoes_totais`, `execucoes_validas` e `falhas_por_categoria`.
- `saidas_invalidas` e `taxa_saida_invalida`: categorias `json_invalido` e `outro` divididas por `execucoes_totais`. O denominador inclui também tentativas de infraestrutura, cujas categorias são contadas à parte.
- `por_tipo`, com as mesmas contagens e métricas separadas por tipo.

`infra_503`, `infra_429` e `timeout` não contam como saídas inválidas nem entram no acerto por campo; aparecem nas contagens de falhas. O terminal mostra as contagens antes das porcentagens. Cada execução tem `origem` (`nova` ou `reaproveitada`); `modelo_gemini` registra o modelo efetivo e `retomado_de` identifica o relatório de origem, quando há retomada. `falhas_api` contém as falhas individuais.

Nunca altere um gabarito depois de consultar as respostas do modelo.

## Limitações

1. As 15 notas são sintéticas, com PDFs de texto limpo e rótulos explícitos; o resultado não representa o desempenho em notas fiscais reais.
2. Os gabaritos foram escritos a partir dos mesmos registros que geraram os PDFs, antes de qualquer chamada ao Gemini; não foram rotulados à mão olhando para as notas.
3. Só 2 das 15 notas têm degradação visual: `nf_011` tem scan com ruído e `nf_012` tem página inclinada. `data_emissao` tem 14 comparações: `nf_013` não tem data, então o esperado `null` é ignorado.
4. A amostra é pequena: 15 notas. Em métricas por nota, uma diferença de uma nota equivale a 6,67 pontos percentuais.
5. O eval usa um único modelo, o configurado em `GEMINI_MODEL`; a produção pode usar outro. O default de `main.py`, `gemini-flash-latest`, é um alias móvel.
6. O eval mede somente `numero_nota`, `cnpj_emitente`, `valor_total` e `data_emissao`. Não mede a classificação da etapa da obra nem a decisão aprovada/rejeitada.
7. O retry de 429 existe apenas no eval. A produção pode repetir internamente erros 503, mas essas tentativas não são contadas no relatório do eval.
8. `normalizar_campo` trata um ponto único com três casas, como `"1.024"`, como decimal. Isso é ambíguo em notas brasileiras e não é exercitado por este dataset.

## Resultado da rodada final

> Neste conjunto de 15 notas sintéticas, com 3 execuções cada (45 chamadas) e o modelo gemini-3.5-flash-lite, todas as 45 execuções produziram saída válida e todos os campos comparados coincidiram com o gabarito (data_emissao: 14 de 15 notas, porque a nf_013 não tem data). Em uma rodada anterior, 2 execuções falharam (uma com erro de API e uma com saída inválida na nf_014) e não se repetiram nas 45 seguintes; a causa não foi investigada.