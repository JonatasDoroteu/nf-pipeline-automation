UPDATE notas_fiscais
SET
    numero_nota = btrim(numero_nota),
    cnpj_emitente = CASE
        WHEN length(regexp_replace(cnpj_emitente, '\D', '', 'g')) = 14 THEN
            substring(regexp_replace(cnpj_emitente, '\D', '', 'g'), 1, 2) || '.' ||
            substring(regexp_replace(cnpj_emitente, '\D', '', 'g'), 3, 3) || '.' ||
            substring(regexp_replace(cnpj_emitente, '\D', '', 'g'), 6, 3) || '/' ||
            substring(regexp_replace(cnpj_emitente, '\D', '', 'g'), 9, 4) || '-' ||
            substring(regexp_replace(cnpj_emitente, '\D', '', 'g'), 13, 2)
        ELSE cnpj_emitente
    END
WHERE status = 'aprovada';
