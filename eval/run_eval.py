"""Avalia a extração do serviço contra gabaritos preenchidos manualmente."""

import argparse
import asyncio
import importlib
import json
import mimetypes
import os
import sys
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SERVICE_DIR = ROOT / "extraction_service"
NOTAS_DIR = Path(__file__).resolve().parent / "notas"
RESULTADOS_DIR = Path(__file__).resolve().parent / "resultados"
CAMPOS = ("numero_nota", "cnpj_emitente", "valor_total", "data_emissao")
EXTENSOES_SUPORTADAS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


def normalizar_campo(campo: str, valor: Any) -> Any:
    """Padroniza os quatro campos sem alterar os valores originais do relatório."""
    if valor is None:
        return None

    texto = str(valor).strip()
    if not texto:
        return None

    if campo == "cnpj_emitente":
        digitos = "".join(caractere for caractere in texto if caractere.isdigit())
        return digitos or None

    if campo == "numero_nota":
        return texto

    if campo == "data_emissao":
        try:
            return date.fromisoformat(texto[:10]).isoformat()
        except ValueError:
            try:
                return datetime.strptime(texto, "%d/%m/%Y").date().isoformat()
            except ValueError:
                return texto

    if campo == "valor_total":
        texto = texto.replace("R$", "").replace(" ", "").replace("\u00a0", "")
        if "," in texto and "." in texto:
            if texto.rfind(",") > texto.rfind("."):
                texto = texto.replace(".", "").replace(",", ".")
            else:
                texto = texto.replace(",", "")
        elif "," in texto:
            texto = texto.replace(",", ".")

        try:
            valor_decimal = Decimal(texto).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except InvalidOperation:
            return None
        return float(valor_decimal)

    raise ValueError(f"Campo sem regra de normalização: {campo}")


def comparar_campos(esperado: dict[str, Any], extraido: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Compara campo a campo; esperado null significa campo intencionalmente ausente."""
    comparacoes = {}
    for campo in CAMPOS:
        esperado_original = esperado.get(campo)
        extraido_original = extraido.get(campo)
        esperado_normalizado = normalizar_campo(campo, esperado_original)
        extraido_normalizado = normalizar_campo(campo, extraido_original)

        if esperado_original is None:
            acertou = None
            resultado = "ignorado"
        else:
            acertou = esperado_normalizado == extraido_normalizado
            resultado = "acertou" if acertou else "errou"

        comparacoes[campo] = {
            "esperado": esperado_original,
            "extraido": extraido_original,
            "esperado_normalizado": esperado_normalizado,
            "extraido_normalizado": extraido_normalizado,
            "acertou": acertou,
            "resultado": resultado,
        }
    return comparacoes


def _carregar_funcao_de_extracao():
    """Importa a implementação de produção apenas quando o eval fará chamadas reais."""
    if Path.cwd().resolve() != SERVICE_DIR:
        raise RuntimeError("Execute o eval a partir da pasta extraction_service.")
    if str(SERVICE_DIR) not in sys.path:
        sys.path.insert(0, str(SERVICE_DIR))
    modulo = importlib.import_module("main")
    return modulo._extrair_dados_dos_bytes


def _carregar_gabaritos(arquivos: list[Path]) -> dict[str, dict[str, Any]]:
    gabaritos = {}
    for arquivo in arquivos:
        caminho = arquivo.with_suffix(".json")
        if not caminho.is_file():
            raise ValueError(f"Gabarito ausente: {caminho.name}")
        with caminho.open(encoding="utf-8") as entrada:
            gabarito = json.load(entrada)
        if not isinstance(gabarito, dict) or any(campo not in gabarito for campo in CAMPOS):
            raise ValueError(f"Gabarito deve conter os campos: {', '.join(CAMPOS)} ({caminho.name})")
        if any(gabarito[campo] is None for campo in CAMPOS[:3]):
            raise ValueError(f"Preencha número, CNPJ e valor no gabarito: {caminho.name}")
        gabaritos[arquivo.name] = gabarito
    return gabaritos


def _categoria_falha(erro: Exception) -> str:
    nome = type(erro).__name__.lower()
    if "timeout" in nome or "timedout" in nome:
        return "timeout"
    if getattr(erro, "status_code", None) == 422:
        return "json_invalido"
    return "erro_api"


def _percentual(certos: int, total: int) -> float | None:
    return round(certos * 100 / total, 2) if total else None


def _calcular_resumo(registros: list[dict[str, Any]], runs: int) -> dict[str, Any]:
    por_execucao = []
    for numero_execucao in range(1, runs + 1):
        comparacoes = [
            execucao["campos"]
            for nota in registros
            for execucao in nota["execucoes"]
            if execucao["run"] == numero_execucao and "campos" in execucao
        ]
        campos = {}
        for campo in CAMPOS:
            resultados = [item[campo]["acertou"] for item in comparacoes if item[campo]["acertou"] is not None]
            campos[campo] = {
                "acertos": sum(resultados),
                "comparacoes": len(resultados),
                "percentual": _percentual(sum(resultados), len(resultados)),
            }

        todos = [
            item[campo]["acertou"]
            for item in comparacoes
            for campo in CAMPOS
            if item[campo]["acertou"] is not None
        ]
        notas_completas = []
        for nota in registros:
            execucao = next((item for item in nota["execucoes"] if item["run"] == numero_execucao), None)
            if execucao and "campos" in execucao:
                notas_completas.append(
                    all(campo["acertou"] is not False for campo in execucao["campos"].values())
                )

        por_execucao.append(
            {
                "run": numero_execucao,
                "acerto_total_campos": _percentual(sum(todos), len(todos)),
                "notas_completas": _percentual(sum(notas_completas), len(notas_completas)),
                "por_campo": campos,
            }
        )

    media_campos = {}
    for campo in CAMPOS:
        percentuais = [item["por_campo"][campo]["percentual"] for item in por_execucao]
        percentuais = [valor for valor in percentuais if valor is not None]
        media_campos[campo] = round(mean(percentuais), 2) if percentuais else None

    totais = [item["acerto_total_campos"] for item in por_execucao if item["acerto_total_campos"] is not None]
    completas = [item["notas_completas"] for item in por_execucao if item["notas_completas"] is not None]
    return {
        "media_acerto_total_campos": round(mean(totais), 2) if totais else None,
        "media_notas_completas": round(mean(completas), 2) if completas else None,
        "media_por_campo": media_campos,
        "por_execucao": por_execucao,
    }


def _imprimir_resultado(resumo: dict[str, Any], registros: list[dict[str, Any]], falhas: list[dict[str, Any]]) -> None:
    print("\nAcerto médio por campo (média das execuções)")
    print(f"{'Campo':<18} {'Acertos':>10}")
    for campo, percentual in resumo["media_por_campo"].items():
        texto = "sem comparação" if percentual is None else f"{percentual:.2f}%"
        print(f"{campo:<18} {texto:>10}")
    total = resumo["media_acerto_total_campos"]
    completas = resumo["media_notas_completas"]
    print(f"{'Todos os campos':<18} {total if total is not None else 'N/D'}{'%' if total is not None else ''}")
    print(f"{'Notas completas':<18} {completas if completas is not None else 'N/D'}{'%' if completas is not None else ''}")

    print("\nErros de extração")
    erros_encontrados = False
    for nota in registros:
        for execucao in nota["execucoes"]:
            for campo, comparacao in execucao.get("campos", {}).items():
                if comparacao["acertou"] is False:
                    erros_encontrados = True
                    print(
                        f"{nota['arquivo']} run {execucao['run']} | {campo}: "
                        f"esperado={comparacao['esperado']!r} vs extraído={comparacao['extraido']!r}"
                    )
    if not erros_encontrados:
        print("Nenhum campo divergente nas chamadas concluídas.")

    print(f"\nFalhas da API: {len(falhas)}")
    for falha in falhas:
        print(f"{falha['arquivo']} run {falha['run']}: {falha['categoria']}")


def executar(runs: int, pausa: float) -> Path:
    arquivos = sorted(
        arquivo for arquivo in NOTAS_DIR.iterdir()
        if arquivo.is_file() and arquivo.suffix.lower() in EXTENSOES_SUPORTADAS
    )
    if not arquivos:
        raise ValueError(f"Nenhum arquivo de nota suportado em {NOTAS_DIR}")
    gabaritos = _carregar_gabaritos(arquivos)

    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("Defina GEMINI_API_KEY no ambiente antes de executar o eval.")
    extrair = _carregar_funcao_de_extracao()

    registros = [{"arquivo": arquivo.name, "esperado": gabaritos[arquivo.name], "execucoes": []} for arquivo in arquivos]
    falhas = []
    total_chamadas = len(arquivos) * runs
    chamada_atual = 0

    for nota, arquivo in zip(registros, arquivos):
        conteudo = arquivo.read_bytes()
        mime_type = mimetypes.guess_type(arquivo.name)[0] or "application/octet-stream"
        for numero_execucao in range(1, runs + 1):
            chamada_atual += 1
            try:
                resposta = asyncio.run(extrair(conteudo, mime_type))
                extraido = resposta.model_dump() if hasattr(resposta, "model_dump") else dict(resposta)
                campos = comparar_campos(nota["esperado"], extraido)
                nota["execucoes"].append({"run": numero_execucao, "extraido": extraido, "campos": campos})
            except Exception as erro:  # Uma falha não deve interromper as demais notas.
                categoria = _categoria_falha(erro)
                falha = {"arquivo": arquivo.name, "run": numero_execucao, "categoria": categoria}
                falhas.append(falha)
                nota["execucoes"].append({"run": numero_execucao, "falha": categoria})
            if pausa and chamada_atual < total_chamadas:
                time.sleep(pausa)

    resumo = _calcular_resumo(registros, runs)
    RESULTADOS_DIR.mkdir(parents=True, exist_ok=True)
    caminho_relatorio = RESULTADOS_DIR / f"{datetime.now():%Y-%m-%d_%H%M}.json"
    relatorio = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "runs_configurados": runs,
        "pausa_segundos": pausa,
        "normalizacao": {
            "cnpj_emitente": "somente dígitos",
            "data_emissao": "YYYY-MM-DD; também aceita dd/mm/aaaa",
            "valor_total": "float arredondado para 2 casas; vírgula ou ponto decimal",
            "numero_nota": "string, preservando zeros à esquerda",
            "esperado_null": "campo intencionalmente ausente; excluído da taxa de acerto",
        },
        "resumo": resumo,
        "falhas_api": falhas,
        "notas": registros,
    }
    caminho_relatorio.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    _imprimir_resultado(resumo, registros, falhas)
    print(f"\nRelatório salvo em: {caminho_relatorio.relative_to(ROOT)}")
    return caminho_relatorio


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3, help="chamadas por nota (padrão: 3)")
    parser.add_argument("--sleep", type=float, default=0, help="pausa em segundos entre chamadas")
    argumentos = parser.parse_args()
    if argumentos.runs < 1:
        parser.error("--runs precisa ser pelo menos 1")
    if argumentos.sleep < 0:
        parser.error("--sleep não pode ser negativo")
    try:
        executar(argumentos.runs, argumentos.sleep)
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as erro:
        print(f"Erro no eval: {erro}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()