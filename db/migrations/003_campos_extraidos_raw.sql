ALTER TABLE raw_extracoes
    ADD COLUMN IF NOT EXISTS numero_nota_extraido VARCHAR(50);

ALTER TABLE raw_extracoes
    ADD COLUMN IF NOT EXISTS cnpj_extraido VARCHAR(18);
