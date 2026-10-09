from pathlib import Path
import sys

import pytest

EVAL_DIR = Path(__file__).resolve().parents[2] / "eval"
if not EVAL_DIR.is_dir():
    pytest.skip(
        f"evaluation tests require the eval directory, not found at {EVAL_DIR}",
        allow_module_level=True,
    )

sys.path.insert(0, str(EVAL_DIR))

from run_eval import comparar_campos, normalizar_campo


@pytest.mark.parametrize(
    "cnpj",
    ["12.345.678/0001-95", "12345678000195"],
)
def test_normaliza_cnpj_com_e_sem_pontuacao(cnpj):
    assert normalizar_campo("cnpj_emitente", cnpj) == "12345678000195"


def test_normaliza_data_brasileira():
    assert normalizar_campo("data_emissao", "09/03/2025") == "2025-03-09"


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("R$ 1.234,56", 1234.56), ("1234.56", 1234.56)],
)
def test_normaliza_valor_com_virgula_e_ponto(valor, esperado):
    assert normalizar_campo("valor_total", valor) == esperado


def test_campo_extraido_ausente_e_erro_quando_esperado():
    comparacao = comparar_campos(
        {"numero_nota": "0012", "cnpj_emitente": "12345678000195", "valor_total": 10, "data_emissao": "2025-03-09"},
        {"numero_nota": "0012", "cnpj_emitente": "12345678000195", "valor_total": 10},
    )

    assert comparacao["data_emissao"]["acertou"] is False
    assert comparacao["data_emissao"]["extraido"] is None


def test_gabarito_null_nao_entra_na_comparacao():
    comparacao = comparar_campos(
        {"numero_nota": "12", "cnpj_emitente": "12345678000195", "valor_total": 10, "data_emissao": None},
        {"numero_nota": "12", "cnpj_emitente": "12345678000195", "valor_total": 10, "data_emissao": "2025-03-09"},
    )

    assert comparacao["data_emissao"]["resultado"] == "ignorado"
    assert comparacao["data_emissao"]["acertou"] is None