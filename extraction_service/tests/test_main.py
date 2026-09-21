from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import HTTPException

from main import (
    DadosNotaFiscal,
    cnpj_e_valido,
    dados_para_rejeicao,
    normalizar_motivo_rejeicao,
    enforce_rate_limit,
    validar_dados,
    require_api_key,
)


def test_cnpj_valido_com_digitos_verificadores():
    assert cnpj_e_valido("04.252.011/0001-10") is True


def test_cnpj_invalido_com_digito_verificador_incorreto():
    assert cnpj_e_valido("04.252.011/0001-11") is False


def test_cnpj_repetido_e_invalido():
    assert cnpj_e_valido("11.111.111/1111-11") is False


@pytest.mark.parametrize(
    ("dados", "motivo"),
    [
        (DadosNotaFiscal(), "Número da nota não identificado"),
        (
            DadosNotaFiscal(numero_nota="123", cnpj_emitente="invalido"),
            "CNPJ inválido ou não identificado",
        ),
        (
            DadosNotaFiscal(
                numero_nota="123",
                cnpj_emitente="04.252.011/0001-10",
                valor_total=0,
            ),
            "Valor total inválido (zero, negativo ou ausente)",
        ),
        (
            DadosNotaFiscal(
                numero_nota="123",
                cnpj_emitente="04.252.011/0001-10",
                valor_total=10,
                data_emissao="data-invalida",
            ),
            "Data de emissão inválida",
        ),
    ],
)
def test_validacao_rejeita_dados_invalidos_sem_consultar_duplicidade(dados, motivo, monkeypatch):
    monkeypatch.setattr("main.nota_ja_existe", lambda *_: pytest.fail("não deveria consultar duplicidade"))

    resultado = validar_dados(dados)

    assert resultado.valido is False
    assert resultado.motivo == motivo


def test_validacao_rejeita_data_futura(monkeypatch):
    monkeypatch.setattr("main.nota_ja_existe", lambda *_: False)
    dados = DadosNotaFiscal(
        numero_nota="123",
        cnpj_emitente="04.252.011/0001-10",
        valor_total=10,
        data_emissao="2999-01-01",
    )

    resultado = validar_dados(dados)

    assert resultado.valido is False
    assert resultado.motivo == "Data de emissão está no futuro"


def test_validacao_rejeita_nota_duplicada(monkeypatch):
    monkeypatch.setattr("main.nota_ja_existe", lambda *_: True)
    dados = DadosNotaFiscal(
        numero_nota="123",
        cnpj_emitente="04.252.011/0001-10",
        valor_total=10,
        data_emissao=date.today().isoformat(),
    )

    resultado = validar_dados(dados)

    assert resultado.valido is False
    assert resultado.motivo == "Nota fiscal duplicada (já processada antes)"


def test_validacao_aprova_nota_valida(monkeypatch):
    monkeypatch.setattr("main.nota_ja_existe", lambda *_: False)
    dados = DadosNotaFiscal(
        numero_nota="123",
        cnpj_emitente="04.252.011/0001-10",
        valor_total=10,
        data_emissao=date.today().isoformat(),
    )

    resultado = validar_dados(dados)

    assert resultado.valido is True
    assert resultado.motivo is None


def test_fallback_de_rejeicao_preenche_campos_obrigatorios():
    rejeicao = dados_para_rejeicao(DadosNotaFiscal())

    assert rejeicao.numero_nota.startswith("REJEITADA-")
    assert rejeicao.cnpj_emitente == "00.000.000/0000-00"
    assert rejeicao.valor_total == 0.01
    assert rejeicao.data_emissao == "1900-01-01"


def test_fallback_de_rejeicao_gera_numeros_unicos():
    primeira = dados_para_rejeicao(DadosNotaFiscal())
    segunda = dados_para_rejeicao(DadosNotaFiscal())

    assert primeira.numero_nota != segunda.numero_nota


def test_normaliza_motivo_de_rejeicao():
    assert normalizar_motivo_rejeicao("` Número inválido `") == "Número inválido"


def test_api_key_ausente_e_rejeitada(monkeypatch):
    monkeypatch.setattr("main.API_AUTH_TOKEN", "token-de-teste")

    with pytest.raises(HTTPException) as erro:
        require_api_key(None)

    assert erro.value.status_code == 401


def test_api_key_valida_e_aceita(monkeypatch):
    monkeypatch.setattr("main.API_AUTH_TOKEN", "token-de-teste")

    assert require_api_key("token-de-teste") == "token-de-teste"


def test_rate_limit_bloqueia_excesso_de_chamadas(monkeypatch):
    monkeypatch.setattr("main.RATE_LIMIT_REQUESTS", 2)
    monkeypatch.setattr("main.RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr("main._rate_limit_requests", {})

    enforce_rate_limit("token-de-teste")
    enforce_rate_limit("token-de-teste")

    with pytest.raises(HTTPException) as erro:
        enforce_rate_limit("token-de-teste")

    assert erro.value.status_code == 429
    assert erro.value.headers["Retry-After"]
    assert erro.value.headers["X-RateLimit-Remaining"] == "0"


def test_rate_limit_e_separado_por_api_key(monkeypatch):
    monkeypatch.setattr("main.RATE_LIMIT_REQUESTS", 1)
    monkeypatch.setattr("main.RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr("main._rate_limit_requests", {})

    enforce_rate_limit("primeiro-token")
    enforce_rate_limit("segundo-token")