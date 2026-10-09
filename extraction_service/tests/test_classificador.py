from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from classificador import classificar


@pytest.mark.parametrize(
    ("descricao", "etapa"),
    [
        ("Serviço de terraplenagem do lote", "Preliminares"),
        ("Execução de sapata isolada", "Fundação"),
        ("Concreto armado para pilar", "Estrutura"),
        ("Bloco cerâmico para alvenaria", "Alvenaria"),
        ("Compra de telha cerâmica", "Telhado"),
        ("Tubulação hidráulica em PVC", "Hidráulica"),
        ("Disjuntor para quadro de distribuição", "Elétrica"),
        ("Instalação de janela de alumínio", "Esquadrias"),
        ("Aplicação de tinta acrílica", "Acabamento"),
    ],
)
def test_classifica_uma_descricao_por_etapa(descricao, etapa):
    assert classificar(descricao) == etapa


def test_classifica_texto_com_acentos():
    assert classificar("Instalação de tubulação hidráulica") == "Hidráulica"


@pytest.mark.parametrize("descricao", ["", "   ", None])
def test_descricao_vazia_retorna_none(descricao):
    assert classificar(descricao) is None


def test_texto_desconhecido_retorna_none():
    assert classificar("Serviço administrativo sem material de obra") is None


def test_etapa_com_prioridade_maior_vence_em_descricao_ambigua():
    assert classificar("Sapata de concreto armado") == "Fundação"


@pytest.mark.parametrize(
    ("descricao", "etapa"),
    [
        ("sapatas de concreto armado e aço para armadura", "Fundação"),
        ("cabos flexíveis, eletrodutos e disjuntores", "Elétrica"),
        ("tubos PVC soldável, conexões hidráulicas", "Hidráulica"),
        ("estrutura de cobertura", "Telhado"),
    ],
)
def test_classifica_descricao_com_variacoes_de_plural_e_termo_especifico(descricao, etapa):
    assert classificar(descricao) == etapa


@pytest.mark.parametrize(
    ("descricao", "etapa"),
    [
        ("disjuntores", "Elétrica"),
        ("pilares", "Estrutura"),
        ("interruptores", "Elétrica"),
        ("portas e janelas", "Esquadrias"),
    ],
)
def test_classifica_plurais_terminados_em_res_e_zes(descricao, etapa):
    assert classificar(descricao) == etapa


@pytest.mark.parametrize("descricao", ["mais", "gás"])
def test_nao_classifica_palavras_semelhantes_aos_finais_de_plural(descricao):
    assert classificar(descricao) is None
