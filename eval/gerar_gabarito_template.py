"""Cria gabaritos vazios para notas novas sem sobrescrever respostas existentes."""

import json
from pathlib import Path


NOTAS_DIR = Path(__file__).resolve().parent / "notas"
EXTENSOES_SUPORTADAS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
CAMPOS = ("numero_nota", "cnpj_emitente", "valor_total", "data_emissao")


def main() -> None:
    notas = sorted(
        arquivo for arquivo in NOTAS_DIR.iterdir()
        if arquivo.is_file() and arquivo.suffix.lower() in EXTENSOES_SUPORTADAS
    )
    criado = 0
    preservado = 0
    template = {campo: None for campo in CAMPOS}

    for nota in notas:
        gabarito = nota.with_suffix(".json")
        if gabarito.exists():
            preservado += 1
            continue
        gabarito.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        criado += 1

    print(f"Templates criados: {criado}; gabaritos existentes preservados: {preservado}.")


if __name__ == "__main__":
    main()