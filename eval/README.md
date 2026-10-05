# Eval de extração

O conjunto contém 15 notas **sintéticas**. Os PDFs e seus gabaritos vêm dos mesmos registros definidos em `gerar_notas_sinteticas.py`; nenhum gabarito é preenchido com saída do Gemini. Os nomes e documentos são fictícios, e os CNPJs têm dígitos verificadores calculados. Ainda assim, o teste é mais fácil que notas reais: os documentos são curtos, controlados e contêm os campos em posições intencionais.

## Preparar os dados

Para recriar os PDFs sintéticos e gabaritos a partir dos dados-fonte:

```powershell
python ../eval/gerar_notas_sinteticas.py
```

Para criar gabaritos vazios para novas notas colocadas em `eval/notas/`, sem sobrescrever gabaritos existentes:

```powershell
python ../eval/gerar_gabarito_template.py
```

Preencha manualmente `numero_nota`, `cnpj_emitente` e `valor_total`. Use `null` em `data_emissao` somente quando a nota realmente não trouxer a data. Gabaritos sem número, CNPJ ou valor são recusados pelo runner.

## Executar

No PowerShell, entre em `extraction_service` e rode:

```powershell
python ../eval/run_eval.py --runs 3 --sleep 1
```

`GEMINI_API_KEY` precisa estar previamente definida no ambiente do terminal. O runner chama a função assíncrona `_extrair_dados_dos_bytes` usada por `/extract`, sem enviar requisições HTTP ao FastAPI. `--runs` define quantas extrações são feitas por arquivo (padrão `3`); `--sleep` define a pausa, em segundos, entre chamadas (padrão `0`).

## Normalização e métricas

- CNPJ: remove pontuação e compara somente os dígitos.
- Data: compara como `YYYY-MM-DD`; também converte `dd/mm/aaaa`.
- Valor: converte vírgula ou ponto decimal para número com duas casas. Quando ambos aparecem, considera decimal o separador mais à direita.
- Número da nota: compara como string e preserva zeros à esquerda.
- Campo com `null` no gabarito é intencionalmente ausente e fica fora do denominador daquele campo. Campo ausente na saída do Gemini, quando havia valor esperado, conta como erro.

O resultado mostra a média das taxas de acerto de cada execução, a taxa geral entre campos e a taxa de notas completas. Falhas de chamada, como timeout ou JSON inválido, são contabilizadas separadamente; o script continua para as próximas tentativas. Os detalhes são salvos em `eval/resultados/AAAA-MM-DD_HHMM.json`. As falhas registram somente a categoria, não o texto da exceção nem variáveis de ambiente.

## Testes

Na pasta `extraction_service`:

```powershell
python -m pytest -q
```

Os testes do eval cobrem apenas normalização e comparação e não chamam o Gemini.

## Limitações

A amostra tem apenas 15 documentos e mede consistência neste conjunto, não representa a diversidade de emissores, leiautes, digitalizações e qualidade de imagem de documentos reais. Os PDFs sintéticos são deliberadamente mais limpos e previsíveis que a maioria das notas recebidas em produção.

## Resultados