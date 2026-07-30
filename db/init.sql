-- Este arquivo roda automaticamente quando o container do Postgres sobe pela primeira vez.

CREATE TABLE IF NOT EXISTS notas_fiscais (
    id SERIAL PRIMARY KEY,
    numero_nota VARCHAR(50) NOT NULL,
    cnpj_emitente VARCHAR(18) NOT NULL,
    valor_total NUMERIC(12, 2) NOT NULL,
    data_emissao DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'aprovada', -- aprovada | rejeitada
    motivo_rejeicao TEXT,
    dados_brutos_extraidos JSONB,
    criado_em TIMESTAMP NOT NULL DEFAULT NOW(),

    -- evita gravar a mesma nota fiscal duas vezes
    CONSTRAINT nota_unica UNIQUE (numero_nota, cnpj_emitente)
);

CREATE TABLE IF NOT EXISTS log_processamento (
    id SERIAL PRIMARY KEY,
    nota_fiscal_id INTEGER REFERENCES notas_fiscais(id),
    etapa VARCHAR(50) NOT NULL, -- extracao | validacao | gravacao | notificacao
    status VARCHAR(20) NOT NULL, -- sucesso | erro
    detalhes TEXT,
    criado_em TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notas_status ON notas_fiscais(status);
CREATE INDEX IF NOT EXISTS idx_log_nota ON log_processamento(nota_fiscal_id);
