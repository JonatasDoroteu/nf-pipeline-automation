import re
import unicodedata


# A primeira etapa correspondente vence, exceto quando um termo genérico é parte
# de uma expressão mais específica correspondente em outra etapa.
PALAVRAS_CHAVE_POR_ETAPA = {
    "Preliminares": (
        "terraplenagem",
        "sondagem",
        "tapume",
        "locacao da obra",
        "limpeza do terreno",
        "mobilizacao de canteiro",
    ),
    "Fundação": (
        "fundacao",
        "sapata",
        "estaca",
        "broca",
        "baldrame",
        "radier",
        "bloco de fundacao",
    ),
    "Estrutura": (
        "concreto armado",
        "pilar",
        "viga",
        "laje",
        "armacao estrutural",
        "estrutura",
    ),
    "Alvenaria": (
        "alvenaria",
        "bloco ceramico",
        "bloco de concreto",
        "tijolo",
        "argamassa de assentamento",
    ),
    "Telhado": (
        "telhado",
        "telha",
        "madeiramento",
        "estrutura de cobertura",
        "manta para telhado",
        "rufo",
    ),
    "Hidráulica": (
        "hidraulica",
        "tubulacao hidraulica",
        "conexao hidraulica",
        "tubo pvc soldavel",
        "tubo pvc esgoto",
        "registro de gaveta",
        "caixa d'agua",
        "caixa dagua",
    ),
    "Elétrica": (
        "eletrica",
        "fio eletrico",
        "cabo flexivel",
        "disjuntor",
        "eletroduto",
        "tomada",
        "interruptor",
        "quadro de distribuicao",
    ),
    "Esquadrias": (
        "esquadria",
        "janela",
        "porta",
        "batente",
        "marco de porta",
        "vidro temperado",
    ),
    "Acabamento": (
        "acabamento",
        "piso porcelanato",
        "revestimento ceramico",
        "massa corrida",
        "tinta acrilica",
        "rejunte",
        "rodape",
        "azulejo",
    ),
}


def _normalizar(texto: str) -> str:
    texto_sem_acentos = unicodedata.normalize("NFD", texto.lower())
    return "".join(
        caractere
        for caractere in texto_sem_acentos
        if unicodedata.category(caractere) != "Mn"
    )


def _singularizar(token: str) -> str:
    if len(token) > 3:
        if token.endswith("oes"):
            return token[:-3] + "ao"
        if token.endswith("eis"):
            return token[:-3] + "el"
        if token.endswith("ais"):
            return token[:-3] + "al"
        if len(token) > 4 and (token.endswith("res") or token.endswith("zes")):
            return token[:-2]
        if token.endswith("s"):
            return token[:-1]
    return token


def _normalizar_plural(texto: str) -> str:
    return re.sub(r"\w+", lambda match: _singularizar(match.group()), texto)


def _corresponde(texto: str, palavra_chave: str) -> bool:
    padrao = rf"(?<!\w){re.escape(palavra_chave)}(?!\w)"
    return re.search(padrao, texto) is not None


PALAVRAS_POR_ETAPA = {
    etapa: tuple(_normalizar_plural(palavra) for palavra in palavras_chave)
    for etapa, palavras_chave in PALAVRAS_CHAVE_POR_ETAPA.items()
}
TODAS_PALAVRAS = tuple(
    (etapa, palavra)
    for etapa, palavras in PALAVRAS_POR_ETAPA.items()
    for palavra in palavras
)


def classificar(descricao: str) -> str | None:
    texto = _normalizar_plural(_normalizar(descricao or ""))
    if not texto.strip():
        return None

    for etapa, palavras in PALAVRAS_POR_ETAPA.items():
        for palavra in palavras:
            if not _corresponde(texto, palavra):
                continue
            termo_especifico_correspondente = any(
                len(termo) > len(palavra)
                and re.search(rf"(?<!\w){re.escape(palavra)}(?!\w)", termo)
                and _corresponde(texto, termo)
                for _, termo in TODAS_PALAVRAS
            )
            if not termo_especifico_correspondente:
                return etapa

    return None
