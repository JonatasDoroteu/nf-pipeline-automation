import asyncio
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

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
