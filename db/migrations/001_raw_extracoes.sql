CREATE TABLE IF NOT EXISTS raw_extracoes (
    id BIGSERIAL PRIMARY KEY,
    arquivo_hash CHAR(64) NOT NULL,
    resposta_bruta TEXT NOT NULL,
    modelo TEXT NOT NULL,
    versao_prompt TEXT NOT NULL,
    nota_fiscal_id INTEGER NULL REFERENCES notas_fiscais(id),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_extracoes_arquivo_hash
    ON raw_extracoes (arquivo_hash);
