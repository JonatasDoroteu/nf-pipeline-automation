"""
Serviço de Extração, Validação e Gravação de Notas Fiscais.

Endpoints:

1. /extract   -> recebe um arquivo (PDF ou imagem) e devolve os dados estruturados,
                 usando o Gemini (gratuito) pra ler o documento.
2. /validate  -> recebe os dados já extraídos e aplica as REGRAS DE NEGÓCIO
                 (isso não usa IA nenhuma -- é lógica determinística, testável).
3. /process   -> endpoint "tudo em um": recebe o arquivo diretamente, extrai,
                 valida e já grava no banco se estiver tudo certo. Esse é o
                 endpoint que a pessoa (ou um sistema externo) chama na prática.

O n8n entra depois desse processamento: pode ser configurado pra rodar em
horário fixo e consultar `/notas-rejeitadas` pra mandar um resumo por e-mail,
por exemplo -- ou seja, o n8n cuida da parte de orquestração/notificação
agendada, e não precisa lidar com o arquivo binário da nota fiscal.
"""

import os
import re
import json
import uuid
from datetime import date, datetime
from typing import Optional

import psycopg2
import google.generativeai as genai
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Serviço de Extração e Validação de Notas Fiscais")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# ---------------------------------------------------------------------------
# Modelos de dados
# ---------------------------------------------------------------------------

class DadosNotaFiscal(BaseModel):
    numero_nota: Optional[str] = None
    cnpj_emitente: Optional[str] = None
    valor_total: Optional[float] = None
    data_emissao: Optional[str] = None  # formato "YYYY-MM-DD"


class ResultadoValidacao(BaseModel):
    valido: bool
    motivo: Optional[str] = None


# ---------------------------------------------------------------------------
# Etapa 1: Extração (usa IA)
# ---------------------------------------------------------------------------

PROMPT_EXTRACAO = """
Você vai receber uma imagem ou PDF de uma nota fiscal brasileira.
Extraia APENAS os seguintes campos e responda SOMENTE com um JSON válido,
sem markdown, sem texto explicativo, no formato exato abaixo:

{
  "numero_nota": "string",
  "cnpj_emitente": "string (formato 00.000.000/0000-00)",
  "valor_total": number,
  "data_emissao": "YYYY-MM-DD"
}

Se não conseguir identificar algum campo com certeza, use null nesse campo.
"""


@app.post("/extract", response_model=DadosNotaFiscal)
async def extrair_dados(file: UploadFile = File(...)):
    conteudo = await file.read()
    return await _extrair_dados_dos_bytes(conteudo, file.content_type)


class ArquivoBase64(BaseModel):
    file_base64: str
    mime_type: str
    filename: Optional[str] = None


@app.post("/extract-base64", response_model=DadosNotaFiscal)
async def extrair_dados_base64(arquivo: ArquivoBase64):
    """
    Igual ao /extract, mas recebe o arquivo como texto (base64) dentro de um
    JSON comum -- sem multipart/form-data. Existe porque montar multipart
    corretamente em algumas ferramentas de automação (como o n8n) pode ser
    instável dependendo da versão; JSON puro é muito mais previsível.
    """
    import base64
    conteudo = base64.b64decode(arquivo.file_base64)
    return await _extrair_dados_dos_bytes(conteudo, arquivo.mime_type)


async def _extrair_dados_dos_bytes(conteudo: bytes, mime_type: str) -> DadosNotaFiscal:
    if not GEMINI_API_KEY:
        raise HTTPException(500, "GEMINI_API_KEY não configurada no .env")

    model = genai.GenerativeModel("gemini-flash-latest")
    resposta = model.generate_content(
        [
            PROMPT_EXTRACAO,
            {"mime_type": mime_type, "data": conteudo},
        ]
    )

    texto_limpo = resposta.text.strip().removeprefix("```json").removesuffix("```").strip()

    try:
        dados = json.loads(texto_limpo)
    except json.JSONDecodeError:
        raise HTTPException(422, f"Não consegui interpretar a resposta da IA: {resposta.text}")

    return DadosNotaFiscal(**dados)


# ---------------------------------------------------------------------------
# Etapa 2: Validação (lógica pura, sem IA)
# ---------------------------------------------------------------------------

def cnpj_e_valido(cnpj: str) -> bool:
    """Valida o formato e o dígito verificador de um CNPJ."""
    cnpj = re.sub(r"\D", "", cnpj or "")
    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        return False

    def calcular_digito(cnpj_parcial: str, pesos: list) -> int:
        soma = sum(int(d) * p for d, p in zip(cnpj_parcial, pesos))
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    digito1 = calcular_digito(cnpj[:12], pesos1)
    digito2 = calcular_digito(cnpj[:12] + str(digito1), pesos2)

    return cnpj[-2:] == f"{digito1}{digito2}"


def nota_ja_existe(numero_nota: str, cnpj: str) -> bool:
    """Checa duplicidade direto no Postgres."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM notas_fiscais WHERE numero_nota = %s AND cnpj_emitente = %s",
                (numero_nota, cnpj),
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


@app.post("/validate", response_model=ResultadoValidacao)
def validar_dados(dados: DadosNotaFiscal):
    if not dados.numero_nota:
        return ResultadoValidacao(valido=False, motivo="Número da nota não identificado")

    if not cnpj_e_valido(dados.cnpj_emitente):
        return ResultadoValidacao(valido=False, motivo="CNPJ inválido ou não identificado")

    if dados.valor_total is None or dados.valor_total <= 0:
        return ResultadoValidacao(valido=False, motivo="Valor total inválido (zero, negativo ou ausente)")

    try:
        data_nota = date.fromisoformat(dados.data_emissao)
    except (ValueError, TypeError):
        return ResultadoValidacao(valido=False, motivo="Data de emissão inválida")

    if data_nota > date.today():
        return ResultadoValidacao(valido=False, motivo="Data de emissão está no futuro")

    if nota_ja_existe(dados.numero_nota, dados.cnpj_emitente):
        return ResultadoValidacao(valido=False, motivo="Nota fiscal duplicada (já processada antes)")

    return ResultadoValidacao(valido=True)


@app.get("/health")
def health():
    return {"status": "ok"}


class StatusNotaFiscal(BaseModel):
    id: int
    numero_nota: str
    cnpj_emitente: str
    valor_total: float
    data_emissao: date
    status: str
    motivo_rejeicao: Optional[str] = None
    criado_em: datetime


@app.get("/notas/{numero_nota}/status", response_model=StatusNotaFiscal)
def consultar_status(numero_nota: str):
    """Consulta o status e os dados principais de uma nota processada."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, numero_nota, cnpj_emitente, valor_total,
                       data_emissao, status, motivo_rejeicao, criado_em
                FROM notas_fiscais
                     WHERE numero_nota = %s
                         OR dados_brutos_extraidos->>'numero_nota' = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (numero_nota, numero_nota),
            )
            registro = cur.fetchone()
    finally:
        conn.close()

    if registro is None:
        raise HTTPException(404, "Nota fiscal não encontrada")

    return StatusNotaFiscal(
        id=registro[0],
        numero_nota=registro[1],
        cnpj_emitente=registro[2],
        valor_total=registro[3],
        data_emissao=registro[4],
        status=registro[5],
        motivo_rejeicao=registro[6],
        criado_em=registro[7],
    )


# ---------------------------------------------------------------------------
# Etapa 3: Gravação no banco
# ---------------------------------------------------------------------------

def dados_para_rejeicao(dados: DadosNotaFiscal) -> DadosNotaFiscal:
    """Preenche os campos obrigatórios sem perder os dados originais extraídos."""
    try:
        data_emissao = date.fromisoformat(dados.data_emissao).isoformat()
    except (ValueError, TypeError):
        data_emissao = "1900-01-01"

    cnpj = dados.cnpj_emitente or "00.000.000/0000-00"
    if len(cnpj) > 18:
        cnpj = "00.000.000/0000-00"

    return DadosNotaFiscal(
        numero_nota=f"REJEITADA-{uuid.uuid4().hex}",
        cnpj_emitente=cnpj,
        valor_total=dados.valor_total if dados.valor_total is not None else 0.01,
        data_emissao=data_emissao,
    )


def normalizar_motivo_rejeicao(motivo: Optional[str]) -> Optional[str]:
    """Remove marcadores de markdown e espaços acidentais do motivo persistido."""
    if motivo is None:
        return None
    return motivo.replace("`", "").strip()


def gravar_nota_fiscal(
    dados: DadosNotaFiscal,
    status: str,
    motivo: Optional[str] = None,
    dados_brutos: Optional[DadosNotaFiscal] = None,
) -> int:
    """Grava a nota fiscal (aprovada ou rejeitada) e retorna o id gerado."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notas_fiscais
                    (numero_nota, cnpj_emitente, valor_total, data_emissao, status, motivo_rejeicao, dados_brutos_extraidos)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (numero_nota, cnpj_emitente) DO NOTHING
                RETURNING id
                """,
                (
                    dados.numero_nota,
                    dados.cnpj_emitente,
                    dados.valor_total,
                    dados.data_emissao,
                    status,
                    normalizar_motivo_rejeicao(motivo),
                    json.dumps((dados_brutos or dados).model_dump()),
                ),
            )
            resultado = cur.fetchone()
            conn.commit()
            return resultado[0] if resultado else None
    finally:
        conn.close()


def registrar_log(nota_fiscal_id: Optional[int], etapa: str, status: str, detalhes: str = ""):
    """Grava uma linha de auditoria na tabela log_processamento."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO log_processamento (nota_fiscal_id, etapa, status, detalhes)
                VALUES (%s, %s, %s, %s)
                """,
                (nota_fiscal_id, etapa, status, detalhes),
            )
            conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Etapa 4: Endpoint único (extrai + valida + grava)
# ---------------------------------------------------------------------------

class ResultadoProcessamento(BaseModel):
    status: str  # "aprovada" | "rejeitada" | "erro"
    dados_extraidos: Optional[DadosNotaFiscal] = None
    motivo: Optional[str] = None
    nota_fiscal_id: Optional[int] = None


@app.post("/process", response_model=ResultadoProcessamento)
async def processar_documento(file: UploadFile = File(...)):
    # 1. Extração
    try:
        dados = await extrair_dados(file)
        registrar_log(None, "extracao", "sucesso")
    except HTTPException as erro:
        registrar_log(None, "extracao", "erro", str(erro.detail))
        return ResultadoProcessamento(status="erro", motivo=f"Falha na extração: {erro.detail}")

    # 2. Validação
    resultado_validacao = validar_dados(dados)

    if not resultado_validacao.valido:
        registrar_log(None, "validacao", "erro", resultado_validacao.motivo)
        dados_rejeicao = dados_para_rejeicao(dados)
        nota_id = gravar_nota_fiscal(
            dados_rejeicao,
            status="rejeitada",
            motivo=resultado_validacao.motivo,
            dados_brutos=dados,
        )
        return ResultadoProcessamento(
            status="rejeitada",
            dados_extraidos=dados,
            motivo=resultado_validacao.motivo,
            nota_fiscal_id=nota_id,
        )

    # 3. Gravação (aprovada)
    registrar_log(None, "validacao", "sucesso")
    nota_id = gravar_nota_fiscal(dados, status="aprovada")
    registrar_log(nota_id, "gravacao", "sucesso")

    return ResultadoProcessamento(
        status="aprovada",
        dados_extraidos=dados,
        nota_fiscal_id=nota_id,
    )
