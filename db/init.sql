-- Este arquivo roda automaticamente quando o container do Postgres sobe pela primeira vez.

CREATE TABLE IF NOT EXISTS obras (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS etapas (
    id SERIAL PRIMARY KEY,
    obra_id INTEGER NOT NULL REFERENCES obras(id),
    nome VARCHAR(100) NOT NULL,
    orcamento_planejado NUMERIC(12, 2) NOT NULL,
    CONSTRAINT etapa_obra_nome_unica UNIQUE (obra_id, nome)
);

CREATE TABLE IF NOT EXISTS notas_fiscais (
    id SERIAL PRIMARY KEY,
    numero_nota VARCHAR(50) NOT NULL,
    cnpj_emitente VARCHAR(18) NOT NULL,
    valor_total NUMERIC(12, 2) NOT NULL,
    data_emissao DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'aprovada', -- aprovada | rejeitada
    motivo_rejeicao TEXT,
    dados_brutos_extraidos JSONB,
    obra_id INTEGER REFERENCES obras(id),
    etapa_id INTEGER REFERENCES etapas(id),
    criado_em TIMESTAMP NOT NULL DEFAULT NOW(),

    -- evita gravar a mesma nota fiscal duas vezes
    CONSTRAINT nota_unica UNIQUE (numero_nota, cnpj_emitente)
);

INSERT INTO obras (nome)
VALUES ('Casa 60m2 (simulada)')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO etapas (obra_id, nome, orcamento_planejado)
SELECT obra.id, etapa.nome, etapa.orcamento_planejado
FROM obras AS obra
CROSS JOIN (
    VALUES
        ('Preliminares', 15415.69),
        ('Fundação', 5929.11),
        ('Estrutura', 17787.33),
        ('Alvenaria', 10672.40),
        ('Telhado', 7114.93),
        ('Hidráulica', 11858.22),
        ('Elétrica', 9486.58),
        ('Esquadrias', 8300.75),
        ('Acabamento', 32017.19)
) AS etapa(nome, orcamento_planejado)
WHERE obra.nome = 'Casa 60m2 (simulada)'
ON CONFLICT (obra_id, nome) DO NOTHING;

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
