import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import psycopg2


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit(
        "Defina DATABASE_URL, por exemplo: "
        "postgresql://nf_user:nf_password@localhost:5432/nf_pipeline"
    )


def inserir_nota(barreira, numero_nota):
    conn = psycopg2.connect(DATABASE_URL)
    try:
        barreira.wait(timeout=10)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notas_fiscais
                    (numero_nota, cnpj_emitente, valor_total, data_emissao, status)
                VALUES (%s, %s, %s, %s, 'aprovada')
                ON CONFLICT (numero_nota, cnpj_emitente) DO NOTHING
                RETURNING id
                """,
                (numero_nota, "04.252.011/0001-10", 1, date.today()),
            )
            inseriu = cur.fetchone() is not None
            conn.commit()
            return inseriu
    finally:
        conn.close()


numero_nota = f"CONC-{uuid.uuid4().hex}"
cnpj_emitente = "04.252.011/0001-10"
barreira = threading.Barrier(2)

try:
    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = list(
            executor.map(
                lambda _: inserir_nota(barreira, numero_nota),
                range(2),
            )
        )

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM notas_fiscais
                WHERE numero_nota = %s AND cnpj_emitente = %s
                """,
                (numero_nota, cnpj_emitente),
            )
            quantidade = cur.fetchone()[0]
    finally:
        conn.close()

    if resultados.count(True) != 1 or resultados.count(False) != 1 or quantidade != 1:
        raise SystemExit(
            f"Falha: inserções={resultados}, linhas encontradas={quantidade}"
        )
    print("OK: uma thread inseriu a nota e a outra recebeu conflito.")
finally:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM notas_fiscais
                WHERE numero_nota = %s AND cnpj_emitente = %s
                """,
                (numero_nota, cnpj_emitente),
            )
            conn.commit()
    finally:
        conn.close()
