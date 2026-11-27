"""Avalia a extração contra gabaritos escritos a partir dos registros das notas sintéticas."""

import argparse
import asyncio
import importlib
import json
import mimetypes
import os
import re
import sys
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from statistics import mean
from typing import Any, Callable

from dotenv import load_dotenv
from fastapi import HTTPException
from google.api_core.exceptions import (
    DeadlineExceeded,
    ResourceExhausted,
    ServiceUnavailable,
    TooManyRequests,
)
from requests.exceptions import Timeout as RequestTimeout


ROOT = Path(__file__).resolve().parents[1]
SERVICE_DIR = ROOT / "extraction_service"
NOTAS_DIR = Path(__file__).resolve().parent / "notas"
RESULTADOS_DIR = Path(__file__).resolve().parent / "resultados"
CAMPOS = ("numero_nota", "cnpj_emitente", "valor_total", "data_emissao")
EXTENSOES_SUPORTADAS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
CATEGORIAS_FALHA = ("infra_503", "infra_429", "timeout", "json_invalido", "outro")


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
    return modulo._extrair_dados_dos_bytes, modulo.MODELO_GEMINI


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


def _carregar_relatorio_retomada(
    caminho: str | Path,
    modelo_gemini: str,
) -> tuple[Path, dict[str, Any]]:
    caminho_origem = Path(caminho).expanduser().resolve()
    with caminho_origem.open(encoding="utf-8") as entrada:
        relatorio = json.load(entrada)
    if not isinstance(relatorio, dict):
        raise ValueError("O arquivo de retomada não contém um relatório JSON válido.")
    if "modelo_gemini" not in relatorio:
        raise ValueError(
            "O relatório de retomada não registra modelo_gemini; não é possível validar o modelo."
        )
    if relatorio["modelo_gemini"] != modelo_gemini:
        raise ValueError(
            "Modelo incompatível no relatório de retomada: "
            f"arquivo={relatorio['modelo_gemini']!r}, atual={modelo_gemini!r}."
        )
    if not isinstance(relatorio.get("notas"), list):
        raise ValueError("O relatório de retomada não contém uma lista válida de notas.")
    return caminho_origem, relatorio


def _categoria_falha(erro: Exception) -> str:
    causa = erro.__cause__
    if getattr(erro, "status_code", None) == 422:
        return "json_invalido"
    if getattr(erro, "status_code", None) == 429 or isinstance(
        erro, (ResourceExhausted, TooManyRequests)
    ) or isinstance(causa, (ResourceExhausted, TooManyRequests)):
        return "infra_429"
    if getattr(erro, "status_code", None) == 503 or isinstance(
        erro, ServiceUnavailable
    ) or isinstance(causa, ServiceUnavailable):
        return "infra_503"
    if (
        getattr(erro, "status_code", None) == 504
        or isinstance(erro, (DeadlineExceeded, RequestTimeout))
        or isinstance(causa, (DeadlineExceeded, RequestTimeout))
    ):
        return "timeout"
    nomes = (type(erro).__name__, type(causa).__name__ if causa else "")
    if any("timeout" in nome.lower() or "timedout" in nome.lower() for nome in nomes):
        return "timeout"
    return "outro"


def _deve_repetir_429(erro: Exception) -> bool:
    return (
        isinstance(erro, HTTPException)
        and erro.status_code == 502
        and isinstance(erro.__cause__, (ResourceExhausted, TooManyRequests))
    )


def _mensagem_falha(erro: Exception) -> str:
    detalhe = erro.detail if isinstance(erro, HTTPException) else str(erro)
    mensagem = str(detalhe)
    mensagem = re.sub(r"https?://[^\s\"'<>]+", "[URL removida]", mensagem, flags=re.IGNORECASE)
    mensagem = re.sub(
        r"(?is)\bheaders?\s*[:=]\s*(?:\{.*?\}|Headers?\(.*?\))",
        "[cabeçalhos removidos]",
        mensagem,
    )
    mensagem = re.sub(
        r"(?im)\b(?:authorization|proxy-authorization|x-goog-api-key|x-api-key|api[\s_-]?key|cookie|set-cookie)\b\s*[:=]\s*[^,\r\n}]+",
        "[cabeçalho removido]",
        mensagem,
    )
    mensagem = re.sub(
        r"(?m)\b([A-Z][A-Z0-9_]{2,})\s*=\s*[^,\r\n}]+",
        r"\1=[variável removida]",
        mensagem,
    )
    mensagem = re.sub(
        r"(?m)(['\"]?[A-Z][A-Z0-9_]{2,}['\"]?\s*:\s*)[^,\r\n}]+",
        r"\1[variável removida]",
        mensagem,
    )
    return mensagem[:200]


def _executar_com_retry_429(
    extrair: Callable[[bytes, str], Any],
    conteudo: bytes,
    mime_type: str,
    max_tentativas: int,
) -> tuple[Any | None, int, Exception | None]:
    for tentativa in range(1, max_tentativas + 1):
        try:
            return asyncio.run(extrair(conteudo, mime_type)), tentativa, None
        except Exception as erro:
            if not _deve_repetir_429(erro) or tentativa == max_tentativas:
                return None, tentativa, erro
            time.sleep(2 ** (tentativa - 1))
    raise ValueError("--max-tentativas precisa ser pelo menos 1")


def _percentual(certos: int, total: int) -> float | None:
    return round(certos * 100 / total, 2) if total else None


def _contar_execucoes(execucoes: list[dict[str, Any]]) -> dict[str, Any]:
    falhas_por_categoria = {categoria: 0 for categoria in CATEGORIAS_FALHA}
    execucoes_validas = 0
    for execucao in execucoes:
        if "campos" in execucao:
            execucoes_validas += 1
            continue
        categoria = execucao.get("falha", "outro")
        if categoria not in falhas_por_categoria:
            categoria = "outro"
        falhas_por_categoria[categoria] += 1

    execucoes_totais = len(execucoes)
    saidas_invalidas = falhas_por_categoria["json_invalido"] + falhas_por_categoria["outro"]
    return {
        "execucoes_totais": execucoes_totais,
        "execucoes_validas": execucoes_validas,
        "saidas_invalidas": saidas_invalidas,
        "taxa_saida_invalida": _percentual(saidas_invalidas, execucoes_totais),
        "falhas_por_categoria": falhas_por_categoria,
    }


def _calcular_resumo_base(registros: list[dict[str, Any]], runs: int) -> dict[str, Any]:
    por_execucao = []
    for numero_execucao in range(1, runs + 1):
        execucoes_run = [
            execucao
            for nota in registros
            for execucao in nota["execucoes"]
            if execucao["run"] == numero_execucao
        ]
        contagens_run = _contar_execucoes(execucoes_run)
        comparacoes = [
            execucao["campos"]
            for execucao in execucoes_run
            if "campos" in execucao
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
                **contagens_run,
                "acerto_total_campos": _percentual(sum(todos), len(todos)),
                "notas_completas": _percentual(sum(notas_completas), len(notas_completas)),
                "notas_completas_acertos": sum(notas_completas),
                "notas_completas_comparacoes": len(notas_completas),
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
    execucoes = [execucao for nota in registros for execucao in nota["execucoes"]]
    return {
        **_contar_execucoes(execucoes),
        "media_acerto_total_campos": round(mean(totais), 2) if totais else None,
        "media_notas_completas": round(mean(completas), 2) if completas else None,
        "media_por_campo": media_campos,
        "por_execucao": por_execucao,
    }


def _calcular_resumo(registros: list[dict[str, Any]], runs: int) -> dict[str, Any]:
    resumo = _calcular_resumo_base(registros, runs)
    registros_por_tipo: dict[str, list[dict[str, Any]]] = {}
    for nota in registros:
        tipo = nota.get("tipo", "nao_informado")
        registros_por_tipo.setdefault(tipo, []).append(nota)
    resumo["por_tipo"] = {
        tipo: _calcular_resumo_base(registros_do_tipo, runs)
        for tipo, registros_do_tipo in registros_por_tipo.items()
    }
    return resumo


def _imprimir_resultado(resumo: dict[str, Any], registros: list[dict[str, Any]], falhas: list[dict[str, Any]]) -> None:
    def imprimir_contagens(rotulo: str, contagens: dict[str, Any]) -> None:
        print(
            f"{rotulo}: execuções válidas {contagens['execucoes_validas']}/"
            f"{contagens['execucoes_totais']}; saídas inválidas "
            f"{contagens['saidas_invalidas']}/{contagens['execucoes_totais']}; "
            f"falhas {contagens['falhas_por_categoria']}"
        )

    print("\nContagens antes das porcentagens")
    imprimir_contagens("Geral", resumo)
    for tipo, resumo_tipo in resumo["por_tipo"].items():
        imprimir_contagens(f"Tipo {tipo}", resumo_tipo)
    for execucao in resumo["por_execucao"]:
        contagens_campos = ", ".join(
            f"{campo}={dados['acertos']}/{dados['comparacoes']}"
            for campo, dados in execucao["por_campo"].items()
        )
        print(
            f"Run {execucao['run']}: notas completas "
            f"{execucao['notas_completas_acertos']}/"
            f"{execucao['notas_completas_comparacoes']}; {contagens_campos}"
        )

    print("\nAcerto médio por campo (média das execuções)")
    print(f"{'Campo':<18} {'Acertos':>10}")
    for campo, percentual in resumo["media_por_campo"].items():
        texto = "sem comparação" if percentual is None else f"{percentual:.2f}%"
        print(f"{campo:<18} {texto:>10}")
    total = resumo["media_acerto_total_campos"]
    completas = resumo["media_notas_completas"]
    print(f"{'Todos os campos':<18} {total if total is not None else 'N/D'}{'%' if total is not None else ''}")
    print(f"{'Notas completas':<18} {completas if completas is not None else 'N/D'}{'%' if completas is not None else ''}")
    taxa_saida_invalida = resumo["taxa_saida_invalida"]
    taxa_texto = "N/D" if taxa_saida_invalida is None else f"{taxa_saida_invalida:.2f}%"
    print(
        f"Saída inválida: {resumo['saidas_invalidas']}/{resumo['execucoes_totais']} "
        f"({taxa_texto})"
    )
    for tipo, resumo_tipo in resumo["por_tipo"].items():
        taxa_tipo = resumo_tipo["taxa_saida_invalida"]
        taxa_tipo_texto = "N/D" if taxa_tipo is None else f"{taxa_tipo:.2f}%"
        acerto_tipo = resumo_tipo["media_acerto_total_campos"]
        acerto_tipo_texto = "N/D" if acerto_tipo is None else f"{acerto_tipo:.2f}%"
        print(
            f"Tipo {tipo}: acerto campos {acerto_tipo_texto}; saída inválida "
            f"{resumo_tipo['saidas_invalidas']}/{resumo_tipo['execucoes_totais']} "
            f"({taxa_tipo_texto})"
        )

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


def executar(
    runs: int,
    pausa: float,
    max_tentativas: int = 3,
    resume: str | Path | None = None,
) -> Path:
    load_dotenv(dotenv_path=ROOT / ".env", override=False)

    arquivos = sorted(
        arquivo for arquivo in NOTAS_DIR.iterdir()
        if arquivo.is_file() and arquivo.suffix.lower() in EXTENSOES_SUPORTADAS
    )
    if not arquivos:
        raise ValueError(f"Nenhum arquivo de nota suportado em {NOTAS_DIR}")
    gabaritos = _carregar_gabaritos(arquivos)

    extrair, modelo_gemini = _carregar_funcao_de_extracao()
    if os.getenv("GEMINI_MODEL") is None:
        print(
            "Aviso: GEMINI_MODEL não está definida; usando o padrão configurado em main.py "
            f"({modelo_gemini}).",
            file=sys.stderr,
        )

    caminho_retomada = None
    relatorio_anterior = None
    execucoes_anteriores: dict[tuple[str, int], dict[str, Any]] = {}
    if resume is not None:
        caminho_retomada, relatorio_anterior = _carregar_relatorio_retomada(
            resume,
            modelo_gemini,
        )
        runs_anteriores = relatorio_anterior.get("runs_configurados")
        if isinstance(runs_anteriores, int) and runs < runs_anteriores:
            print(
                f"Aviso: --runs={runs} é menor que runs_configurados={runs_anteriores} "
                "no relatório; runs extras serão ignorados.",
                file=sys.stderr,
            )
        arquivos_atuais = {arquivo.name for arquivo in arquivos}
        for nota_anterior in relatorio_anterior["notas"]:
            if not isinstance(nota_anterior, dict):
                raise ValueError("O relatório de retomada contém uma nota inválida.")
            arquivo_anterior = nota_anterior.get("arquivo")
            if arquivo_anterior not in arquivos_atuais:
                continue
            execucoes_anteriores_nota = nota_anterior.get("execucoes", [])
            if not isinstance(execucoes_anteriores_nota, list):
                raise ValueError(
                    f"Execuções inválidas no relatório de retomada: {arquivo_anterior}."
                )
            for execucao_anterior in execucoes_anteriores_nota:
                if not isinstance(execucao_anterior, dict):
                    raise ValueError(
                        f"Execução inválida no relatório de retomada: {arquivo_anterior}."
                    )
                numero_run = execucao_anterior.get("run")
                if (
                    not isinstance(numero_run, int)
                    or not 1 <= numero_run <= runs
                    or "extraido" not in execucao_anterior
                ):
                    continue
                extraido_anterior = execucao_anterior["extraido"]
                if not isinstance(extraido_anterior, dict):
                    raise ValueError(
                        f"Extração inválida no relatório de retomada: "
                        f"{arquivo_anterior}, run {numero_run}."
                    )
                execucoes_anteriores[(arquivo_anterior, numero_run)] = execucao_anterior

    registros = [
        {
            "arquivo": arquivo.name,
            "tipo": gabaritos[arquivo.name].get("tipo", "nao_informado"),
            "esperado": gabaritos[arquivo.name],
            "execucoes": [],
        }
        for arquivo in arquivos
    ]
    falhas = []
    total_chamadas = sum(
        (arquivo.name, numero_run) not in execucoes_anteriores
        for arquivo in arquivos
        for numero_run in range(1, runs + 1)
    )
    if total_chamadas and not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("Defina GEMINI_API_KEY no ambiente antes de executar o eval.")
    chamada_atual = 0

    for nota, arquivo in zip(registros, arquivos):
        conteudo = arquivo.read_bytes()
        mime_type = mimetypes.guess_type(arquivo.name)[0] or "application/octet-stream"
        for numero_execucao in range(1, runs + 1):
            execucao_anterior = execucoes_anteriores.get((arquivo.name, numero_execucao))
            if execucao_anterior is not None:
                extraido = execucao_anterior["extraido"]
                campos = comparar_campos(nota["esperado"], extraido)
                nota["execucoes"].append(
                    {
                        "run": numero_execucao,
                        "tentativas": execucao_anterior.get("tentativas", 0),
                        "origem": "reaproveitada",
                        "extraido": extraido,
                        "campos": campos,
                    }
                )
                continue

            chamada_atual += 1
            resposta, tentativas, erro = _executar_com_retry_429(
                extrair,
                conteudo,
                mime_type,
                max_tentativas,
            )
            try:
                if erro is not None:
                    raise erro
                extraido = resposta.model_dump() if hasattr(resposta, "model_dump") else dict(resposta)
                campos = comparar_campos(nota["esperado"], extraido)
                nota["execucoes"].append(
                    {
                        "run": numero_execucao,
                        "tentativas": tentativas,
                        "origem": "nova",
                        "extraido": extraido,
                        "campos": campos,
                    }
                )
            except Exception as erro:  # Uma falha não deve interromper as demais notas.
                categoria = _categoria_falha(erro)
                detalhes_erro = {
                    "tipo_excecao": type(erro).__name__,
                    "tipo_causa": type(erro.__cause__).__name__ if erro.__cause__ else None,
                    "mensagem": _mensagem_falha(erro),
                }
                falha = {
                    "arquivo": arquivo.name,
                    "run": numero_execucao,
                    "tentativas": tentativas,
                    "categoria": categoria,
                    **detalhes_erro,
                }
                falhas.append(falha)
                nota["execucoes"].append(
                    {
                        "run": numero_execucao,
                        "tentativas": tentativas,
                        "origem": "nova",
                        "falha": categoria,
                        **detalhes_erro,
                    }
                )
            if pausa and chamada_atual < total_chamadas:
                time.sleep(pausa)

    resumo = _calcular_resumo(registros, runs)
    RESULTADOS_DIR.mkdir(parents=True, exist_ok=True)
    agora = datetime.now()
    caminho_relatorio = RESULTADOS_DIR / f"{agora:%Y-%m-%d_%H%M}.json"
    if caminho_relatorio.exists():
        caminho_relatorio = RESULTADOS_DIR / f"{agora:%Y-%m-%d_%H%M%S}.json"
        sufixo = 1
        while caminho_relatorio.exists():
            caminho_relatorio = RESULTADOS_DIR / f"{agora:%Y-%m-%d_%H%M%S}_{sufixo}.json"
            sufixo += 1
    relatorio = {
        "gerado_em": agora.isoformat(timespec="seconds"),
        "modelo_gemini": modelo_gemini,
        "runs_configurados": runs,
        "max_tentativas": max_tentativas,
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
    if caminho_retomada is not None:
        relatorio["retomado_de"] = caminho_retomada.name
    caminho_relatorio.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    _imprimir_resultado(resumo, registros, falhas)
    print(f"\nRelatório salvo em: {caminho_relatorio.relative_to(ROOT)}")
    return caminho_relatorio


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3, help="chamadas por nota (padrão: 3)")
    parser.add_argument("--sleep", type=float, default=0, help="pausa em segundos entre chamadas")
    parser.add_argument(
        "--max-tentativas",
        type=int,
        default=3,
        help="máximo de tentativas do eval para erros 429 (padrão: 3)",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        help="retoma resultados de um relatório anterior sem repetir extrações concluídas",
    )
    argumentos = parser.parse_args()
    if argumentos.runs < 1:
        parser.error("--runs precisa ser pelo menos 1")
    if argumentos.sleep < 0:
        parser.error("--sleep não pode ser negativo")
    if argumentos.max_tentativas < 1:
        parser.error("--max-tentativas precisa ser pelo menos 1")
    try:
        executar(
            argumentos.runs,
            argumentos.sleep,
            argumentos.max_tentativas,
            argumentos.resume,
        )
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as erro:
        print(f"Erro no eval: {erro}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()