from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import main


def test_calcular_resumo_custos_aplica_limite_de_alerta_e_separa_sem_classificacao():
    resumo = main.calcular_resumo_custos(
        [
            ("Fundação", Decimal("1000.00"), Decimal("900.00")),
            ("Estrutura", Decimal("2000.00"), Decimal("1799.00")),
        ],
        Decimal("75.50"),
    )

    assert resumo["etapas"] == [
        {
            "nome": "Fundação",
            "orcamento_planejado": 1000.0,
            "gasto": 900.0,
            "percentual": 0.9,
            "alerta": True,
        },
        {
            "nome": "Estrutura",
            "orcamento_planejado": 2000.0,
            "gasto": 1799.0,
            "percentual": 0.8995,
            "alerta": False,
        },
    ]
    assert resumo["sem_classificacao"] == {"gasto": 75.5}


def test_resumo_exige_api_key(monkeypatch):
    monkeypatch.setattr(main, "API_AUTH_TOKEN", "token-de-teste")

    resposta = TestClient(main.app).get("/obras/1/resumo")

    assert resposta.status_code == 401


def test_resumo_retorna_404_para_obra_inexistente(monkeypatch):
    class CursorFalso:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, *_):
            pass

        def fetchone(self):
            return None

    class ConexaoFalsa:
        def cursor(self):
            return CursorFalso()

        def close(self):
            pass

    monkeypatch.setattr(main, "API_AUTH_TOKEN", "token-de-teste")
    monkeypatch.setattr(main.psycopg2, "connect", lambda *_: ConexaoFalsa())

    resposta = TestClient(main.app).get(
        "/obras/999/resumo",
        headers={"X-API-Key": "token-de-teste"},
    )

    assert resposta.status_code == 404


def test_resumo_retorna_etapas_e_gastos_aprovados(monkeypatch):
    class CursorFalso:
        def __init__(self):
            self.consulta = ""

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, consulta, *_):
            self.consulta = consulta

        def fetchone(self):
            if "FROM obras" in self.consulta:
                return (1,)
            return (Decimal("50.00"),)

        def fetchall(self):
            assert "nota.status = 'aprovada'" in self.consulta
            return [("Acabamento", Decimal("100.00"), Decimal("90.00"))]

    class ConexaoFalsa:
        def cursor(self):
            return CursorFalso()

        def close(self):
            pass

    monkeypatch.setattr(main, "API_AUTH_TOKEN", "token-de-teste")
    monkeypatch.setattr(main.psycopg2, "connect", lambda *_: ConexaoFalsa())

    resposta = TestClient(main.app).get(
        "/obras/1/resumo",
        headers={"X-API-Key": "token-de-teste"},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {
        "obra_id": 1,
        "etapas": [
            {
                "nome": "Acabamento",
                "orcamento_planejado": 100.0,
                "gasto": 90.0,
                "percentual": 0.9,
                "alerta": True,
            }
        ],
        "sem_classificacao": {"gasto": 50.0},
    }
