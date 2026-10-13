import asyncio
import base64
import hashlib
import json
import sys
import threading
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from google.api_core.exceptions import ResourceExhausted
from fastapi.testclient import TestClient
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


class RelogioFalso:
    def __init__(self):
        self.agora = 0
        self.esperas = []

    def monotonic(self):
        return self.agora

    def avancar(self, segundos):
        self.agora += segundos

    async def sleep(self, segundos):
        self.esperas.append(segundos)
        self.avancar(segundos)


def usar_relogio_falso(monkeypatch):
    relogio = RelogioFalso()
    monkeypatch.setattr(main.time, "monotonic", relogio.monotonic)
    monkeypatch.setattr(main.asyncio, "sleep", relogio.sleep)

    async def executar_sem_thread(funcao, *args, **kwargs):
        return funcao(*args, **kwargs)

    monkeypatch.setattr(main.asyncio, "to_thread", executar_sem_thread)
    return relogio


def preparar_extracao(monkeypatch, texto, connect):
    chamadas = []

    def generate_content(_, **kwargs):
        chamadas.append((threading.get_ident(), kwargs))
        return SimpleNamespace(text=texto)

    monkeypatch.setattr(main, "GEMINI_API_KEY", "token-de-teste")
    monkeypatch.setattr(main.psycopg2, "connect", connect)
    monkeypatch.setattr(
        main.genai,
        "GenerativeModel",
        lambda nome: SimpleNamespace(generate_content=generate_content),
    )
    return chamadas


def preparar_cliente_gemini_mock(monkeypatch):
    texto = json.dumps({"numero_nota": "123"})
    modelo = SimpleNamespace(
        generate_content=lambda *_args, **_kwargs: SimpleNamespace(text=texto)
    )
    cliente_gemini = Mock(return_value=modelo)
    monkeypatch.setattr(main, "GEMINI_API_KEY", "token-de-teste")
    monkeypatch.setattr(main.genai, "GenerativeModel", cliente_gemini)
    monkeypatch.setattr(main.psycopg2, "connect", lambda *_: FakeConnection([]))
    return cliente_gemini


def test_grava_raw_quando_extracao_tem_sucesso(monkeypatch):
    texto = '  {"numero_nota":"123"}  '
    inserts = []
    chamadas = preparar_extracao(
        monkeypatch,
        texto,
        lambda _: FakeConnection(inserts),
    )

    resultado = asyncio.run(main._extrair_dados_dos_bytes(b"arquivo", "image/png"))

    assert resultado.numero_nota == "123"
    assert resultado.descricao_itens == ""
    assert len(inserts) == 2
    insert_query, insert_values = inserts[0]
    assert "INSERT INTO raw_extracoes" in insert_query
    assert insert_values == (
        hashlib.sha256(b"arquivo").hexdigest(),
        texto,
        "gemini-flash-latest",
        "v2",
    )
    update_query, update_values = inserts[1]
    assert "UPDATE raw_extracoes" in update_query
    assert update_values == ("123", None, hashlib.sha256(b"arquivo").hexdigest())
    thread_id, kwargs = chamadas[0]
    assert thread_id != threading.get_ident()
    assert kwargs["request_options"] == {
        "timeout": main.ATTEMPT_TIMEOUT_S,
        "retry": None,
    }


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


def test_extract_base64_registra_duracao_tipo_e_status_sem_conteudo(monkeypatch, caplog):
    conteudo_privado = b"CONTEUDO-PRIVADO-DO-PDF"

    async def extrair_com_falha(*_args):
        try:
            raise main.RequestTimeout("mensagem privada")
        except main.RequestTimeout as causa:
            raise HTTPException(504, "timeout") from causa

    monkeypatch.setattr(main, "_extrair_dados_dos_bytes", extrair_com_falha)
    arquivo = main.ArquivoBase64(
        file_base64=base64.b64encode(conteudo_privado).decode("ascii"),
        mime_type="application/pdf",
    )

    with pytest.raises(HTTPException) as erro:
        asyncio.run(main.extrair_dados_base64(arquivo))

    assert erro.value.status_code == 504
    assert "/extract-base64 falhou: duracao=" in caplog.text
    assert "tipo=Timeout status=504" in caplog.text
    assert conteudo_privado.decode() not in caplog.text
    assert arquivo.file_base64 not in caplog.text


@pytest.mark.parametrize(
    ("conteudo", "mime_type", "status_code", "detail"),
    [
        (b"", "application/pdf", 400, "O arquivo está vazio"),
        (b"conteudo", "text/plain", 415, "Tipo de arquivo não suportado"),
    ],
)
def test_extract_base64_rejeita_entrada_invalida_sem_chamar_gemini(
    monkeypatch,
    conteudo,
    mime_type,
    status_code,
    detail,
):
    monkeypatch.setattr(main, "API_AUTH_TOKEN", "token-de-teste")
    cliente_gemini = preparar_cliente_gemini_mock(monkeypatch)
    resposta = TestClient(main.app).post(
        "/extract-base64",
        headers={"X-API-Key": "token-de-teste"},
        json={
            "file_base64": base64.b64encode(conteudo).decode("ascii"),
            "mime_type": mime_type,
        },
    )

    cliente_gemini.assert_not_called()
    assert resposta.status_code == status_code
    assert resposta.json() == {"detail": detail}


def test_extract_base64_rejeita_arquivo_acima_do_limite_sem_chamar_gemini(monkeypatch):
    monkeypatch.setattr(main, "API_AUTH_TOKEN", "token-de-teste")
    monkeypatch.setattr(main, "MAX_UPLOAD_SIZE_BYTES", 4, raising=False)
    cliente_gemini = preparar_cliente_gemini_mock(monkeypatch)
    resposta = TestClient(main.app).post(
        "/extract-base64",
        headers={"X-API-Key": "token-de-teste"},
        json={
            "file_base64": base64.b64encode(b"%PDF-").decode("ascii"),
            "mime_type": "application/pdf",
        },
    )

    cliente_gemini.assert_not_called()
    assert resposta.status_code == 413
    assert resposta.json() == {"detail": "O arquivo excede o tamanho máximo permitido"}


def test_extract_base64_aceita_pdf_valido_com_gemini_mockado(monkeypatch):
    monkeypatch.setattr(main, "API_AUTH_TOKEN", "token-de-teste")
    texto = json.dumps({"numero_nota": "123"})
    inserts = []
    chamadas = preparar_extracao(
        monkeypatch,
        texto,
        lambda _: FakeConnection(inserts),
    )
    resposta = TestClient(main.app).post(
        "/extract-base64",
        headers={"X-API-Key": "token-de-teste"},
        json={
            "file_base64": base64.b64encode(b"%PDF-1.7 documento de teste").decode("ascii"),
            "mime_type": "application/pdf",
        },
    )

    assert resposta.status_code == 200
    assert resposta.json()["numero_nota"] == "123"
    assert len(chamadas) == 1


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


def test_normaliza_cnpj_sem_pontuacao():
    assert main.normalizar_cnpj("12345678000195") == "12.345.678/0001-95"


def test_cnpj_ja_formatado_permanece_igual():
    assert main.normalizar_cnpj("12.345.678/0001-95") == "12.345.678/0001-95"


def test_cnpj_com_quantidade_de_digitos_diferente_permanece_igual():
    assert main.normalizar_cnpj("cnpj inválido") == "cnpj inválido"


def test_normaliza_numero_nota_sem_remover_zeros():
    assert main.normalizar_numero_nota("  00123  ") == "00123"


def test_extracao_retorna_cnpj_e_numero_normalizados(monkeypatch):
    texto = json.dumps(
        {
            "numero_nota": "  00123  ",
            "cnpj_emitente": "12345678000195",
            "valor_total": 10,
            "data_emissao": "2025-03-09",
        }
    )
    preparar_extracao(
        monkeypatch,
        texto,
        lambda _: FakeConnection([]),
    )

    resultado = asyncio.run(main._extrair_dados_dos_bytes(b"arquivo", "image/png"))

    assert resultado.numero_nota == "00123"
    assert resultado.cnpj_emitente == "12.345.678/0001-95"


def test_timeout_do_gemini_retorna_504(monkeypatch):
    usar_relogio_falso(monkeypatch)
    monkeypatch.setattr(main, "GEMINI_API_KEY", "token-de-teste")

    def expirar(*_args, **_kwargs):
        raise main.DeadlineExceeded("timeout")

    monkeypatch.setattr(
        main.genai,
        "GenerativeModel",
        lambda _: SimpleNamespace(generate_content=expirar),
    )

    with pytest.raises(HTTPException) as erro:
        asyncio.run(main._extrair_dados_dos_bytes(b"arquivo", "image/png"))

    assert erro.value.status_code == 504
    assert "50 segundos" in erro.value.detail


def test_timeout_http_do_gemini_retorna_504(monkeypatch):
    usar_relogio_falso(monkeypatch)
    monkeypatch.setattr(main, "GEMINI_API_KEY", "token-de-teste")

    def expirar(*_args, **_kwargs):
        raise main.RequestTimeout()

    monkeypatch.setattr(
        main.genai,
        "GenerativeModel",
        lambda _: SimpleNamespace(generate_content=expirar),
    )

    with pytest.raises(HTTPException) as erro:
        asyncio.run(main._extrair_dados_dos_bytes(b"arquivo", "image/png"))

    assert erro.value.status_code == 504


def test_falha_da_api_gemini_retorna_502(monkeypatch):
    monkeypatch.setattr(main, "GEMINI_API_KEY", "token-de-teste")

    def falhar(*_args, **_kwargs):
        raise main.GoogleAPICallError("api unavailable")

    monkeypatch.setattr(
        main.genai,
        "GenerativeModel",
        lambda _: SimpleNamespace(generate_content=falhar),
    )

    with pytest.raises(HTTPException) as erro:
        asyncio.run(main._extrair_dados_dos_bytes(b"arquivo", "image/png"))

    assert erro.value.status_code == 502


def test_falha_de_rede_do_gemini_retorna_502(monkeypatch):
    monkeypatch.setattr(main, "GEMINI_API_KEY", "token-de-teste")

    def falhar(*_args, **_kwargs):
        raise main.RequestException()

    monkeypatch.setattr(
        main.genai,
        "GenerativeModel",
        lambda _: SimpleNamespace(generate_content=falhar),
    )

    with pytest.raises(HTTPException) as erro:
        asyncio.run(main._extrair_dados_dos_bytes(b"arquivo", "image/png"))

    assert erro.value.status_code == 502


def test_timeouts_das_tentativas_respeitam_deadline_total(monkeypatch):
    relogio = usar_relogio_falso(monkeypatch)
    monkeypatch.setattr(main, "GEMINI_API_KEY", "token-de-teste")
    timeouts = []

    def expirar(*_args, **kwargs):
        timeout = kwargs["request_options"]["timeout"]
        timeouts.append(timeout)
        relogio.avancar(timeout)
        raise main.DeadlineExceeded("timeout")

    monkeypatch.setattr(
        main.genai,
        "GenerativeModel",
        lambda _: SimpleNamespace(generate_content=expirar),
    )

    with pytest.raises(HTTPException) as erro:
        asyncio.run(main._extrair_dados_dos_bytes(b"arquivo", "image/png"))

    assert erro.value.status_code == 504
    assert timeouts == [20, 20, 4]
    assert relogio.esperas == [2, 4]
    assert relogio.agora == main.TOTAL_DEADLINE_S


def test_gemini_503_tenta_duas_vezes_antes_do_sucesso(monkeypatch):
    relogio = usar_relogio_falso(monkeypatch)
    monkeypatch.setattr(main, "GEMINI_API_KEY", "token-de-teste")
    monkeypatch.setattr(main.psycopg2, "connect", lambda _: FakeConnection([]))
    chamadas = []

    def generate_content(*_args, **_kwargs):
        chamadas.append(None)
        if len(chamadas) < 3:
            raise main.ServiceUnavailable("busy")
        return SimpleNamespace(text='{"numero_nota":"123"}')

    monkeypatch.setattr(
        main.genai,
        "GenerativeModel",
        lambda _: SimpleNamespace(generate_content=generate_content),
    )

    resultado = asyncio.run(main._extrair_dados_dos_bytes(b"arquivo", "image/png"))

    assert resultado.numero_nota == "123"
    assert len(chamadas) == 3
    assert relogio.esperas == [2, 4]


def test_429_nao_tenta_novamente(monkeypatch):
    relogio = usar_relogio_falso(monkeypatch)
    monkeypatch.setattr(main, "GEMINI_API_KEY", "token-de-teste")
    chamadas = []

    def quota_esgotada(*_args, **_kwargs):
        chamadas.append(None)
        raise ResourceExhausted("quota exhausted")

    monkeypatch.setattr(
        main.genai,
        "GenerativeModel",
        lambda _: SimpleNamespace(generate_content=quota_esgotada),
    )

    with pytest.raises(HTTPException) as erro:
        asyncio.run(main._extrair_dados_dos_bytes(b"arquivo", "image/png"))

    assert erro.value.status_code == 502
    assert len(chamadas) == 1
    assert relogio.esperas == []
