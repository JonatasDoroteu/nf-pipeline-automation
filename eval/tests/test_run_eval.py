import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from google.api_core.exceptions import (
    DeadlineExceeded,
    ResourceExhausted,
    ServiceUnavailable,
    TooManyRequests,
)
from requests.exceptions import Timeout as RequestTimeout


EVAL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL_DIR))

import run_eval


EXPECTED = {
    "numero_nota": "00000123",
    "cnpj_emitente": "12.000.001/0001-15",
    "valor_total": 1024.5,
    "data_emissao": "2025-01-15",
    "tipo": "limpo",
}
EXTRAIDO = {campo: EXPECTED[campo] for campo in run_eval.CAMPOS}


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("12.345.678/0001-95", "12345678000195"),
        ("12345678000195", "12345678000195"),
    ],
)
def test_normalizar_cnpj_com_e_sem_pontuacao(valor, esperado):
    assert run_eval.normalizar_campo("cnpj_emitente", valor) == esperado


@pytest.mark.parametrize(
    "valor",
    ["2025-03-09", "09/03/2025"],
)
def test_normalizar_data_iso_e_brasileira(valor):
    assert run_eval.normalizar_campo("data_emissao", valor) == "2025-03-09"


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("1.024,50", 1024.5),
        ("1024.50", 1024.5),
        ("R$ 810.00", 810.0),
        ("10.999,99", 10999.99),
    ],
)
def test_normalizar_valores_total(valor, esperado):
    assert run_eval.normalizar_campo("valor_total", valor) == esperado


def test_normalizar_valor_com_ponto_unico_e_tres_casas():
    # "1.024" é lido como decimal e retorna 1.02; pode também significar 1024, portanto é ambíguo.
    assert run_eval.normalizar_campo("valor_total", "1.024") == 1.02


def test_normalizar_numero_nota_preserva_zeros_a_esquerda():
    normalizado = run_eval.normalizar_campo("numero_nota", "00000123")

    assert normalizado == "00000123"
    assert normalizado != run_eval.normalizar_campo("numero_nota", "123")


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("numero_nota", None),
        ("cnpj_emitente", None),
        ("valor_total", None),
        ("data_emissao", None),
        ("numero_nota", ""),
        ("cnpj_emitente", ""),
        ("valor_total", ""),
        ("data_emissao", ""),
    ],
)
def test_normalizar_none_e_string_vazia(campo, valor):
    assert run_eval.normalizar_campo(campo, valor) is None


def test_comparar_campos_acerto_erro_e_data_ausente():
    esperado = {
        "numero_nota": "00123",
        "cnpj_emitente": "12.345.678/0001-95",
        "valor_total": 810.0,
        "data_emissao": None,
    }
    extraido = {
        "numero_nota": "00123",
        "cnpj_emitente": "12345678000195",
        "valor_total": 800.0,
        "data_emissao": "2025-03-09",
    }

    comparacao = run_eval.comparar_campos(esperado, extraido)

    assert comparacao["numero_nota"]["resultado"] == "acertou"
    assert comparacao["cnpj_emitente"]["acertou"] is True
    assert comparacao["valor_total"]["resultado"] == "errou"
    assert comparacao["data_emissao"]["resultado"] == "ignorado"
    assert comparacao["data_emissao"]["acertou"] is None


def _campos(acertos):
    return {
        campo: {"acertou": acertos.get(campo, True)}
        for campo in run_eval.CAMPOS
    }


def test_calcular_resumo_por_campo_notas_falhas_e_tipos():
    registros = [
        {
            "arquivo": "nf_001.pdf",
            "tipo": "limpo",
            "execucoes": [{"run": 1, "campos": _campos({})}],
        },
        {
            "arquivo": "nf_002.pdf",
            "tipo": "limpo",
            "execucoes": [
                {"run": 1, "campos": _campos({"numero_nota": False})}
            ],
        },
        {
            "arquivo": "nf_003.pdf",
            "tipo": "scan_ruido",
            "execucoes": [{"run": 1, "falha": "infra_503"}],
        },
        {
            "arquivo": "nf_004.pdf",
            "execucoes": [{"run": 1, "campos": _campos({})}],
        },
    ]

    resumo = run_eval._calcular_resumo(registros, runs=1)
    execucao = resumo["por_execucao"][0]

    assert execucao["por_campo"]["numero_nota"] == {
        "acertos": 2,
        "comparacoes": 3,
        "percentual": 66.67,
    }
    assert execucao["acerto_total_campos"] == 91.67
    assert execucao["notas_completas"] == 66.67
    assert resumo["execucoes_totais"] == 4
    assert resumo["execucoes_validas"] == 3
    assert resumo["saidas_invalidas"] == 0
    assert resumo["taxa_saida_invalida"] == 0.0
    assert resumo["falhas_por_categoria"] == {
        "infra_503": 1,
        "infra_429": 0,
        "timeout": 0,
        "json_invalido": 0,
        "outro": 0,
    }
    assert resumo["por_tipo"]["limpo"]["media_acerto_total_campos"] == 87.5
    assert resumo["por_tipo"]["scan_ruido"]["media_acerto_total_campos"] is None
    assert resumo["por_tipo"]["nao_informado"]["media_notas_completas"] == 100.0
    assert resumo["por_tipo"]["scan_ruido"]["falhas_por_categoria"]["infra_503"] == 1
    assert resumo["por_tipo"]["nao_informado"]["execucoes_totais"] == 1


def test_taxa_saida_invalida_usa_total_incluindo_falhas_de_infra():
    registros = [
        {"arquivo": "nf_001.pdf", "tipo": "limpo", "execucoes": [{"run": 1, "campos": _campos({})}]},
        {"arquivo": "nf_002.pdf", "tipo": "limpo", "execucoes": [{"run": 1, "falha": "json_invalido"}]},
        {"arquivo": "nf_003.pdf", "tipo": "limpo", "execucoes": [{"run": 1, "falha": "outro"}]},
        {"arquivo": "nf_004.pdf", "tipo": "limpo", "execucoes": [{"run": 1, "falha": "infra_503"}]},
        {"arquivo": "nf_005.pdf", "tipo": "limpo", "execucoes": [{"run": 1, "falha": "infra_429"}]},
        {"arquivo": "nf_006.pdf", "tipo": "limpo", "execucoes": [{"run": 1, "falha": "timeout"}]},
    ]

    resumo = run_eval._calcular_resumo(registros, runs=1)

    assert resumo["execucoes_totais"] == 6
    assert resumo["execucoes_validas"] == 1
    assert resumo["saidas_invalidas"] == 2
    assert resumo["taxa_saida_invalida"] == 33.33
    assert resumo["por_tipo"]["limpo"]["falhas_por_categoria"]["timeout"] == 1


def test_terminal_imprime_contagens_antes_das_porcentagens(capsys):
    registros = [
        {
            "arquivo": f"nf_{numero:03d}.pdf",
            "tipo": "limpo",
            "execucoes": [{"run": 1, "campos": _campos({})}],
        }
        for numero in range(1, 14)
    ]
    registros.extend(
        [
            {
                "arquivo": "nf_014.pdf",
                "tipo": "limpo",
                "execucoes": [{"run": 1, "falha": "json_invalido"}],
            },
            {
                "arquivo": "nf_015.pdf",
                "tipo": "limpo",
                "execucoes": [{"run": 1, "falha": "infra_503"}],
            },
        ]
    )
    resumo = run_eval._calcular_resumo(registros, runs=1)

    run_eval._imprimir_resultado(resumo, registros, falhas=[])
    saida = capsys.readouterr().out

    assert "execuções válidas 13/15" in saida
    assert "numero_nota=13/13" in saida
    assert saida.index("execuções válidas 13/15") < saida.index("%")


def _http_exception_with_cause(status_code, cause):
    erro = HTTPException(status_code=status_code, detail="erro simulado")
    erro.__cause__ = cause
    return erro


@pytest.mark.parametrize(
    ("erro", "categoria"),
    [
        (_http_exception_with_cause(502, ServiceUnavailable("503")), "infra_503"),
        (_http_exception_with_cause(502, ResourceExhausted("429")), "infra_429"),
        (_http_exception_with_cause(502, TooManyRequests("429")), "infra_429"),
        (DeadlineExceeded("deadline"), "timeout"),
        (RequestTimeout("request timeout"), "timeout"),
        (HTTPException(status_code=422, detail="json inválido"), "json_invalido"),
        (ValueError("erro comum"), "outro"),
    ],
)
def test_categoria_falha(erro, categoria):
    assert run_eval._categoria_falha(erro) == categoria


def test_executar_com_retry_429_esgotado(monkeypatch):
    chamadas = []
    esperas = []

    async def sempre_429(*_):
        chamadas.append(1)
        raise _http_exception_with_cause(502, ResourceExhausted("quota"))

    monkeypatch.setattr(run_eval.time, "sleep", esperas.append)
    resposta, tentativas, erro = run_eval._executar_com_retry_429(
        sempre_429, b"arquivo", "application/pdf", max_tentativas=3
    )

    assert resposta is None
    assert tentativas == 3
    assert run_eval._categoria_falha(erro) == "infra_429"
    assert len(chamadas) == 3
    assert esperas == [1, 2]


def test_executar_com_retry_429_seguido_de_sucesso(monkeypatch):
    chamadas = []
    esperas = []

    async def uma_falha_depois_sucesso(*_):
        chamadas.append(1)
        if len(chamadas) == 1:
            raise _http_exception_with_cause(502, TooManyRequests("quota"))
        return {"ok": True}

    monkeypatch.setattr(run_eval.time, "sleep", esperas.append)
    resposta, tentativas, erro = run_eval._executar_com_retry_429(
        uma_falha_depois_sucesso, b"arquivo", "application/pdf", max_tentativas=3
    )

    assert resposta == {"ok": True}
    assert tentativas == 2
    assert erro is None
    assert esperas == [1]


def test_executar_com_retry_429_nao_repete_503(monkeypatch):
    chamadas = []
    esperas = []

    async def erro_503(*_):
        chamadas.append(1)
        raise _http_exception_with_cause(502, ServiceUnavailable("indisponível"))

    monkeypatch.setattr(run_eval.time, "sleep", esperas.append)
    resposta, tentativas, erro = run_eval._executar_com_retry_429(
        erro_503, b"arquivo", "application/pdf", max_tentativas=3
    )

    assert resposta is None
    assert tentativas == 1
    assert run_eval._categoria_falha(erro) == "infra_503"
    assert len(chamadas) == 1
    assert esperas == []


@pytest.fixture
def eval_workspace(tmp_path, monkeypatch):
    notes_dir = tmp_path / "eval" / "notas"
    results_dir = tmp_path / "eval" / "resultados"
    notes_dir.mkdir(parents=True)
    results_dir.mkdir(parents=True)
    (notes_dir / "nf_001.pdf").write_bytes(b"synthetic pdf")
    (notes_dir / "nf_001.json").write_text(
        json.dumps(EXPECTED),
        encoding="utf-8",
    )
    calls = []

    async def extrair_falso(*_):
        calls.append(1)
        return dict(EXTRAIDO)

    monkeypatch.setattr(run_eval, "ROOT", tmp_path)
    monkeypatch.setattr(run_eval, "NOTAS_DIR", notes_dir)
    monkeypatch.setattr(run_eval, "RESULTADOS_DIR", results_dir)
    monkeypatch.setattr(run_eval, "load_dotenv", lambda **_: None)
    monkeypatch.setattr(run_eval, "_imprimir_resultado", lambda *_: None)
    monkeypatch.setattr(
        run_eval,
        "_carregar_funcao_de_extracao",
        lambda: (extrair_falso, "modelo-teste"),
    )
    monkeypatch.setenv("GEMINI_API_KEY", "chave-falsa-de-teste")
    monkeypatch.setenv("GEMINI_MODEL", "modelo-teste")

    return {
        "root": tmp_path,
        "results_dir": results_dir,
        "calls": calls,
        "extrair": extrair_falso,
    }


def _salvar_relatorio(caminho, modelo="modelo-teste", runs=1, execucoes=None):
    relatorio = {
        "modelo_gemini": modelo,
        "runs_configurados": runs,
        "notas": [
            {
                "arquivo": "nf_001.pdf",
                "execucoes": execucoes or [],
            }
        ],
    }
    caminho.write_text(json.dumps(relatorio), encoding="utf-8")
    return caminho


def test_resume_reaproveita_extraido_recalcula_e_preserva_origem(eval_workspace, monkeypatch):
    fonte = eval_workspace["root"] / "anterior.json"
    execucoes = [
        {
            "run": 1,
            "tentativas": 2,
            "extraido": dict(EXTRAIDO),
            "campos": {"comparacao_antiga": "obsoleta"},
        }
    ]
    _salvar_relatorio(fonte, execucoes=execucoes)
    bytes_origem = fonte.read_bytes()
    monkeypatch.delenv("GEMINI_API_KEY")

    destino = run_eval.executar(runs=1, pausa=0, resume=fonte)
    relatorio = json.loads(destino.read_text(encoding="utf-8"))
    execucao = relatorio["notas"][0]["execucoes"][0]

    assert not eval_workspace["calls"]
    assert destino != fonte
    assert fonte.read_bytes() == bytes_origem
    assert relatorio["retomado_de"] == fonte.name
    assert relatorio["notas"][0]["tipo"] == "limpo"
    assert execucao["origem"] == "reaproveitada"
    assert execucao["tentativas"] == 2
    assert all(campo["acertou"] is True for campo in execucao["campos"].values())
    assert "comparacao_antiga" not in execucao["campos"]


def test_resume_reexecuta_falha_anterior_e_runs_ausentes(eval_workspace):
    fonte = eval_workspace["root"] / "parcial.json"
    _salvar_relatorio(
        fonte,
        runs=2,
        execucoes=[{"run": 1, "falha": "infra_429"}],
    )

    destino = run_eval.executar(runs=2, pausa=0, resume=fonte)
    relatorio = json.loads(destino.read_text(encoding="utf-8"))
    execucoes = relatorio["notas"][0]["execucoes"]

    assert len(eval_workspace["calls"]) == 2
    assert [execucao["origem"] for execucao in execucoes] == ["nova", "nova"]
    assert [execucao["run"] for execucao in execucoes] == [1, 2]
    assert all("campos" in execucao for execucao in execucoes)


@pytest.mark.parametrize(
    ("relatorio", "mensagem"),
    [
        ({"modelo_gemini": "outro-modelo", "runs_configurados": 1, "notas": []}, "Modelo incompatível"),
        ({"runs_configurados": 1, "notas": []}, "não registra modelo_gemini"),
    ],
)
def test_resume_aborta_sem_modelo_compativel(
    eval_workspace,
    tmp_path,
    relatorio,
    mensagem,
):
    fonte = tmp_path / "incompativel.json"
    fonte.write_text(json.dumps(relatorio), encoding="utf-8")

    with pytest.raises(ValueError, match=mensagem):
        run_eval.executar(runs=1, pausa=0, resume=fonte)

    assert not eval_workspace["calls"]
    assert list(eval_workspace["results_dir"].glob("*.json")) == []


def test_relatorio_nao_expoe_chave_ou_url_da_mensagem(eval_workspace, monkeypatch):
    async def falha_com_credenciais(*_):
        raise HTTPException(
            status_code=502,
            detail=(
                "API key: AIzaFAKEKEY123 "
                "URL https://example.test/extract?key=AIzaFAKEKEY123"
            ),
        )

    monkeypatch.setattr(
        run_eval,
        "_carregar_funcao_de_extracao",
        lambda: (falha_com_credenciais, "modelo-teste"),
    )

    destino = run_eval.executar(runs=1, pausa=0, max_tentativas=1)
    texto_relatorio = destino.read_text(encoding="utf-8")

    assert "AIzaFAKEKEY123" not in texto_relatorio
    assert "https://example.test" not in texto_relatorio
    assert "?key=" not in texto_relatorio
