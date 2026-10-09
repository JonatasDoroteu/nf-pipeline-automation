BEGIN;

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

ALTER TABLE notas_fiscais
    ADD COLUMN IF NOT EXISTS obra_id INTEGER REFERENCES obras(id);

ALTER TABLE notas_fiscais
    ADD COLUMN IF NOT EXISTS etapa_id INTEGER REFERENCES etapas(id);

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

COMMIT;
