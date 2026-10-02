import asyncio
import hashlib
import json
import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main


class FakeCursor:
    def __init__(self, inserts):
        self.inserts = inserts

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, values):
        self.inserts.append((query, values))


class FakeConnection:
    def __init__(self, inserts):
        self.inserts = inserts

    def cursor(self):
        return FakeCursor(self.inserts)

    def commit(self):
        pass

    def close(self):
        pass


def preparar_extracao(monkeypatch, texto, connect):
    monkeypatch.setattr(main, "GEMINI_API_KEY", "token-de-teste")
    monkeypatch.setattr(main.psycopg2, "connect", connect)
    monkeypatch.setattr(
        main.genai,
        "GenerativeModel",
        lambda nome: SimpleNamespace(
            generate_content=lambda _: SimpleNamespace(text=texto)
        ),
    )


def test_grava_raw_quando_extracao_tem_sucesso(monkeypatch):
    texto = '  {"numero_nota":"123"}  '
    inserts = []
    preparar_extracao(
        monkeypatch,
        texto,
        lambda _: FakeConnection(inserts),
    )

    resultado = asyncio.run(main._extrair_dados_dos_bytes(b"arquivo", "image/png"))

    assert resultado.numero_nota == "123"
    assert len(inserts) == 1
    query, values = inserts[0]
    assert "INSERT INTO raw_extracoes" in query
    assert values == (
        hashlib.sha256(b"arquivo").hexdigest(),
        texto,
        "gemini-flash-latest",
        "v1",
    )


def test_grava_raw_mesmo_com_json_invalido(monkeypatch):
    texto = "resposta que não é JSON"
    inserts = []
    preparar_extracao(
        monkeypatch,
        texto,
        lambda _: FakeConnection(inserts),
    )

    with pytest.raises(HTTPException) as erro:
        asyncio.run(main._extrair_dados_dos_bytes(b"arquivo", "image/png"))

    assert erro.value.status_code == 422
    assert inserts[0][1][1] == texto


def test_falha_ao_gravar_raw_nao_interrompe_extracao(monkeypatch):
    texto = json.dumps(
        {
            "numero_nota": "123",
            "cnpj_emitente": "04.252.011/0001-10",
            "valor_total": 10,
            "data_emissao": "2025-03-09",
        }
    )
    preparar_extracao(
        monkeypatch,
        texto,
        lambda _: (_ for _ in ()).throw(RuntimeError("banco indisponível")),
    )

    resultado = asyncio.run(main._extrair_dados_dos_bytes(b"arquivo", "image/png"))

    assert resultado.numero_nota == "123"


def test_conflito_no_insert_retorna_rejeitada_e_registra_log(monkeypatch):
    dados = main.DadosNotaFiscal(
        numero_nota="123",
        cnpj_emitente="04.252.011/0001-10",
        valor_total=10,
        data_emissao="2025-03-09",
    )
    logs = []

    async def extrair(_):
        return dados

    monkeypatch.setattr(main, "extrair_dados", extrair)
    monkeypatch.setattr(
        main,
        "validar_dados",
        lambda _: main.ResultadoValidacao(valido=True),
    )
    monkeypatch.setattr(main, "gravar_nota_fiscal", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main, "registrar_log", lambda *args: logs.append(args))
    monkeypatch.setattr(
        main,
        "_atualizar_raw_nota_fiscal",
        lambda *_: pytest.fail("não deve associar raw em conflito"),
    )
    arquivo = UploadFile(file=BytesIO(b"arquivo"), filename="nota.png")

    resultado = asyncio.run(main.processar_documento(arquivo))

    assert resultado.status == "rejeitada"
    assert resultado.motivo == "Nota fiscal duplicada (já processada antes)"
    assert resultado.nota_fiscal_id is None
    assert (None, "gravacao", "erro", resultado.motivo) in logs


def test_falha_ao_atualizar_vinculo_raw_nao_e_lancada(monkeypatch):
    monkeypatch.setattr(
        main.psycopg2,
        "connect",
        lambda *_: (_ for _ in ()).throw(RuntimeError("banco indisponível")),
    )

    main._atualizar_raw_nota_fiscal("a" * 64, 10)
