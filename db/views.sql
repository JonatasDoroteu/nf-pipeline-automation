CREATE OR REPLACE VIEW raw_extracoes_notas_aprovadas AS
SELECT
    r.id AS raw_extracao_id,
    r.arquivo_hash,
    r.resposta_bruta,
    r.modelo,
    r.versao_prompt,
    r.numero_nota_extraido,
    r.cnpj_extraido,
    r.criado_em AS extracao_criada_em,
    n.id AS nota_fiscal_id,
    n.numero_nota,
    n.cnpj_emitente,
    n.valor_total,
    n.data_emissao,
    n.criado_em AS nota_criada_em
FROM raw_extracoes AS r
JOIN notas_fiscais AS n
  ON n.numero_nota = r.numero_nota_extraido
 AND n.cnpj_emitente = r.cnpj_extraido
WHERE n.status = 'aprovada';
