"""Gera PDFs de exemplo e gabaritos somente a partir dos dados sintéticos abaixo."""

import json
import random
import unicodedata
import zlib
from pathlib import Path


NOTAS_DIR = Path(__file__).resolve().parent / "notas"
LARGURA_PAGINA = 595
ALTURA_PAGINA = 842

# Cada registro é a fonte de verdade do PDF e do respectivo gabarito.
REGISTROS = [
    {"numero": "00000123", "fornecedor": "Aurora Papelaria Ltda", "base_cnpj": "120000010001", "valor": 1024.50, "data": "2025-01-15", "data_visual": "15/01/2025", "layout": "limpo", "moeda": "br"},
    {"numero": "123", "fornecedor": "Horizonte Manutencao Ltda", "base_cnpj": "120000020001", "valor": 810.00, "data": "2025-02-03", "data_visual": "2025-02-03", "layout": "limpo", "moeda": "us"},
    {"numero": "0000456", "fornecedor": "Vale Verde Alimentos Ltda", "base_cnpj": "120000030001", "valor": 256.75, "data": "2025-03-09", "data_visual": "09/03/2025", "layout": "limpo", "moeda": "br"},
    {"numero": "78", "fornecedor": "Oficina Central Servicos Ltda", "base_cnpj": "120000040001", "valor": 42.90, "data": "2025-04-21", "data_visual": "2025-04-21", "layout": "limpo", "moeda": "us"},
    {"numero": "0009", "fornecedor": "Nuvem Clara Tecnologia Ltda", "base_cnpj": "120000050001", "valor": 10999.99, "data": "2025-05-14", "data_visual": "14/05/2025", "layout": "limpo", "moeda": "br"},
    {"numero": "1000001", "fornecedor": "Rota Sul Transportes Ltda", "base_cnpj": "120000060001", "valor": 567.00, "data": "2025-06-02", "data_visual": "2025-06-02", "layout": "limpo", "moeda": "us"},
    {"numero": "001234", "fornecedor": "Lago Azul Uniformes Ltda", "base_cnpj": "120000070001", "valor": 3210.08, "data": "2025-07-19", "data_visual": "19/07/2025", "layout": "limpo", "moeda": "br"},
    {"numero": "88", "fornecedor": "Ponte Alta Consultoria Ltda", "base_cnpj": "120000080001", "valor": 75.30, "data": "2025-08-05", "data_visual": "2025-08-05", "layout": "limpo", "moeda": "us"},
    {"numero": "0000007", "fornecedor": "Serra Nova Limpeza Ltda", "base_cnpj": "120000090001", "valor": 980.00, "data": "2025-09-11", "data_visual": "11/09/2025", "layout": "limpo", "moeda": "br"},
    {"numero": "20260015", "fornecedor": "Campo Aberto Equipamentos Ltda", "base_cnpj": "120000100001", "valor": 1400.45, "data": "2025-10-27", "data_visual": "2025-10-27", "layout": "limpo", "moeda": "us"},
    {"numero": "00077", "fornecedor": "Grafica Estrela Ltda", "base_cnpj": "120000110001", "valor": 1250.90, "data": "2025-11-04", "data_visual": "04/11/2025", "layout": "ruido", "moeda": "br"},
    {"numero": "012345", "fornecedor": "Mar Aberto Pecas Ltda", "base_cnpj": "120000120001", "valor": 999.99, "data": "2025-11-12", "data_visual": "2025-11-12", "layout": "rotacionado", "moeda": "us"},
    {"numero": "000013", "fornecedor": "Jardim das Fontes Ltda", "base_cnpj": "120000130001", "valor": 654.32, "data": None, "data_visual": None, "layout": "limpo", "moeda": "br"},
    {"numero": "14", "fornecedor": "Ponto Norte Logistica Ltda", "base_cnpj": "120000140001", "valor": 2875.00, "data": "2025-12-03", "data_visual": "03/12/2025", "layout": "diferente", "moeda": "us"},
    {"numero": "000900", "fornecedor": "Delta Oficina Tecnica Ltda", "base_cnpj": "120000150001", "valor": 1180.45, "data": "2025-12-18", "data_visual": "2025-12-18", "layout": "valores", "moeda": "br"},
]


def calcular_digito(base: str, pesos: list[int]) -> str:
    resto = sum(int(digito) * peso for digito, peso in zip(base, pesos)) % 11
    return "0" if resto < 2 else str(11 - resto)


def cnpj_com_digitos_validos(base: str) -> str:
    primeiro = calcular_digito(base, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    segundo = calcular_digito(base + primeiro, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    digitos = base + primeiro + segundo
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"


def moeda(valor: float, estilo: str) -> str:
    texto = f"{valor:,.2f}"
    if estilo == "br":
        return texto.replace(",", "_").replace(".", ",").replace("_", ".")
    return texto.replace(",", "")


def preparar_registro(registro: dict) -> dict:
    item = dict(registro)
    item["cnpj"] = cnpj_com_digitos_validos(item.pop("base_cnpj"))
    item["arquivo"] = f"nf_{REGISTROS.index(registro) + 1:03}.pdf"
    return item


def linhas_da_nota(item: dict) -> list[str]:
    cnpj = item["cnpj"]
    valor = moeda(item["valor"], item["moeda"])
    data = item["data_visual"]

    if item["layout"] == "diferente":
        return [
            "COMPROVANTE FISCAL - VIA DO CLIENTE",
            f"EMITENTE | {item['fornecedor']}",
            f"CNPJ | {cnpj}",
            f"DOC. NUMERO | {item['numero']}",
            f"EMISSAO | {data}",
            "SERVICO DE TRANSPORTE REGIONAL",
            f"TOTAL A PAGAR | R$ {valor}",
        ]
    if item["layout"] == "valores":
        return [
            "NOTA FISCAL DE SERVICOS",
            f"FORNECEDOR: {item['fornecedor']}",
            f"CNPJ DO EMITENTE: {cnpj}",
            f"NUMERO DA NOTA: {item['numero']}",
            f"DATA DE EMISSAO: {data}",
            "SUBTOTAL DOS SERVICOS: R$ 1.000,00",
            "IMPOSTOS E RETENCOES: R$ 180,45",
            f"VALOR TOTAL DA NOTA: R$ {valor}",
        ]

    linhas = [
        "NOTA FISCAL DE SERVICOS",
        f"FORNECEDOR: {item['fornecedor']}",
        f"CNPJ DO EMITENTE: {cnpj}",
        f"NUMERO DA NOTA: {item['numero']}",
    ]
    if data:
        linhas.append(f"DATA DE EMISSAO: {data}")
    linhas.extend(["DESCRICAO: SERVICOS PRESTADOS", f"VALOR TOTAL: R$ {valor}"])
    return linhas


def texto_pdf(texto: str) -> bytes:
    codificado = texto.encode("cp1252", errors="replace")
    return codificado.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def stream_pdf(dados: bytes, extras: bytes = b"") -> bytes:
    return b"<< /Length " + str(len(dados)).encode() + extras + b" >>\nstream\n" + dados + b"\nendstream"


def montar_pdf(linhas: list[str], layout: str) -> bytes:
    if layout == "ruido":
        imagem = gerar_imagem_ruidosa(linhas)
        conteudo = b"q 595 0 0 842 0 0 cm /Im0 Do Q\n"
        recursos = b"/XObject << /Im0 6 0 R >>"
        objetos = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << " + recursos + b" >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            stream_pdf(conteudo),
            stream_pdf(zlib.compress(imagem), b" /Type /XObject /Subtype /Image /Width 600 /Height 840 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode"),
        ]
    else:
        comandos = []
        if layout == "rotacionado":
            comandos.append(b"q 0.9962 0.0872 -0.0872 0.9962 38 -24 cm")
        for indice, linha in enumerate(linhas):
            y = 790 - indice * 42
            tamanho = 18 if indice == 0 else 12
            comandos.append(
                b"BT /F1 " + str(tamanho).encode() + b" Tf 48 " + str(y).encode()
                + b" Td (" + texto_pdf(linha) + b") Tj ET"
            )
        if layout == "rotacionado":
            comandos.append(b"Q")
        conteudo = b"\n".join(comandos) + b"\n"
        objetos = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            stream_pdf(conteudo),
        ]

    saida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for numero, objeto in enumerate(objetos, start=1):
        offsets.append(len(saida))
        saida.extend(f"{numero} 0 obj\n".encode())
        saida.extend(objeto)
        saida.extend(b"\nendobj\n")

    inicio_xref = len(saida)
    saida.extend(f"xref\n0 {len(objetos) + 1}\n".encode())
    saida.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        saida.extend(f"{offset:010} 00000 n \n".encode())
    saida.extend(
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n".encode()
    )
    return bytes(saida)


GLIFOS = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    ":": ("00000", "00100", "00100", "00000", "00100", "00100", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00110", "00110"),
    ",": ("00000", "00000", "00000", "00000", "00110", "00110", "00100"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
}


def gerar_imagem_ruidosa(linhas: list[str]) -> bytes:
    largura, altura, escala = 600, 840, 2
    aleatorio = random.Random(7341)
    pixels = bytearray(largura * altura * 3)
    for indice in range(largura * altura):
        tom = max(225, min(255, 247 + aleatorio.randint(-7, 7)))
        posicao = indice * 3
        pixels[posicao:posicao + 3] = bytes((tom, tom, tom))

    def ponto(x: int, y: int) -> None:
        if 0 <= x < largura and 0 <= y < altura:
            posicao = (y * largura + x) * 3
            pixels[posicao:posicao + 3] = b"\x38\x38\x38"

    def escrever(texto: str, x: int, y: int) -> None:
        texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()
        for caractere in texto:
            glifo = GLIFOS.get(caractere)
            if glifo:
                for linha, padrao in enumerate(glifo):
                    for coluna, marcado in enumerate(padrao):
                        if marcado == "1":
                            for dy in range(escala):
                                for dx in range(escala):
                                    ponto(x + coluna * escala + dx, y + linha * escala + dy)
            x += 6 * escala

    for indice, linha in enumerate(linhas):
        escrever(linha, 38, 112 + indice * 48)

    for _ in range(3200):
        x = aleatorio.randrange(largura)
        y = aleatorio.randrange(altura)
        tom = aleatorio.choice((110, 145, 180, 210))
        posicao = (y * largura + x) * 3
        pixels[posicao:posicao + 3] = bytes((tom, tom, tom))
    for y in range(60, altura, 91):
        for x in range(largura):
            if aleatorio.random() < 0.18:
                posicao = (y * largura + x) * 3
                pixels[posicao:posicao + 3] = b"\xd8\xd8\xd8"
    return bytes(pixels)


def gerar_pdf(item: dict) -> None:
    conteudo = montar_pdf(linhas_da_nota(item), item["layout"])
    (NOTAS_DIR / item["arquivo"]).write_bytes(conteudo)


def gerar_gabarito(item: dict) -> None:
    gabarito = {
        "numero_nota": item["numero"],
        "cnpj_emitente": item["cnpj"],
        "valor_total": item["valor"],
        "data_emissao": item["data"],
    }
    caminho = NOTAS_DIR / item["arquivo"]
    caminho.with_suffix(".json").write_text(
        json.dumps(gabarito, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def gerar_dados_md(itens: list[dict]) -> None:
    linhas = [
        "# Dados das notas sintéticas",
        "",
        "Todos os nomes, números e valores foram criados para este eval. Os CNPJs foram calculados com dígitos verificadores válidos; não foram consultados em cadastro oficial para verificar se estão livres de uso.",
        "",
        "| Arquivo | Fornecedor fictício | Número impresso | CNPJ sintético | Valor total | Data esperada | Variação |",
        "|---|---|---:|---|---:|---|---|",
    ]
    descricoes = {
        "limpo": "Layout limpo",
        "ruido": "Imagem escaneada com ruído",
        "rotacionado": "Página inclinada",
        "diferente": "Layout de comprovante",
        "valores": "Subtotal, impostos e total",
    }
    for item in itens:
        data = item["data"] or "ausente (null no gabarito)"
        linhas.append(
            f"| {item['arquivo']} | {item['fornecedor']} | {item['numero']} | {item['cnpj']} | "
            f"R$ {moeda(item['valor'], 'br')} | {data} | {descricoes[item['layout']]} |"
        )
    linhas.extend(
        [
            "",
            "Os arquivos JSON pareados foram escritos diretamente a partir dos registros desta rotina, antes de qualquer chamada ao Gemini. A nota `nf_013.pdf` não contém data; seu valor esperado é `null`.",
            "",
        ]
    )
    (NOTAS_DIR / "DADOS.md").write_text("\n".join(linhas), encoding="utf-8")


def main() -> None:
    NOTAS_DIR.mkdir(parents=True, exist_ok=True)
    itens = [preparar_registro(registro) for registro in REGISTROS]
    for item in itens:
        gerar_pdf(item)
        gerar_gabarito(item)
    gerar_dados_md(itens)
    print(f"Notas sintéticas geradas: {len(itens)} PDFs e gabaritos em {NOTAS_DIR}")


if __name__ == "__main__":
    main()