# Dados das notas sintéticas

Todos os nomes, números e valores foram criados para este eval. Os CNPJs foram calculados com dígitos verificadores válidos; não foram consultados em cadastro oficial para verificar se estão livres de uso.

| Arquivo | Fornecedor fictício | Número impresso | CNPJ sintético | Valor total | Data esperada | Variação |
|---|---|---:|---|---:|---|---|
| nf_001.pdf | Aurora Papelaria Ltda | 00000123 | 12.000.001/0001-15 | R$ 1.024,50 | 2025-01-15 | Layout limpo |
| nf_002.pdf | Horizonte Manutencao Ltda | 123 | 12.000.002/0001-60 | R$ 810,00 | 2025-02-03 | Layout limpo |
| nf_003.pdf | Vale Verde Alimentos Ltda | 0000456 | 12.000.003/0001-04 | R$ 256,75 | 2025-03-09 | Layout limpo |
| nf_004.pdf | Oficina Central Servicos Ltda | 78 | 12.000.004/0001-59 | R$ 42,90 | 2025-04-21 | Layout limpo |
| nf_005.pdf | Nuvem Clara Tecnologia Ltda | 0009 | 12.000.005/0001-01 | R$ 10.999,99 | 2025-05-14 | Layout limpo |
| nf_006.pdf | Rota Sul Transportes Ltda | 1000001 | 12.000.006/0001-48 | R$ 567,00 | 2025-06-02 | Layout limpo |
| nf_007.pdf | Lago Azul Uniformes Ltda | 001234 | 12.000.007/0001-92 | R$ 3.210,08 | 2025-07-19 | Layout limpo |
| nf_008.pdf | Ponte Alta Consultoria Ltda | 88 | 12.000.008/0001-37 | R$ 75,30 | 2025-08-05 | Layout limpo |
| nf_009.pdf | Serra Nova Limpeza Ltda | 0000007 | 12.000.009/0001-81 | R$ 980,00 | 2025-09-11 | Layout limpo |
| nf_010.pdf | Campo Aberto Equipamentos Ltda | 20260015 | 12.000.010/0001-06 | R$ 1.400,45 | 2025-10-27 | Layout limpo |
| nf_011.pdf | Grafica Estrela Ltda | 00077 | 12.000.011/0001-50 | R$ 1.250,90 | 2025-11-04 | Imagem escaneada com ruído |
| nf_012.pdf | Mar Aberto Pecas Ltda | 012345 | 12.000.012/0001-03 | R$ 999,99 | 2025-11-12 | Página inclinada |
| nf_013.pdf | Jardim das Fontes Ltda | 000013 | 12.000.013/0001-40 | R$ 654,32 | ausente (null no gabarito) | Layout limpo |
| nf_014.pdf | Ponto Norte Logistica Ltda | 14 | 12.000.014/0001-94 | R$ 2.875,00 | 2025-12-03 | Layout de comprovante |
| nf_015.pdf | Delta Oficina Tecnica Ltda | 000900 | 12.000.015/0001-39 | R$ 1.180,45 | 2025-12-18 | Subtotal, impostos e total |

Os arquivos JSON pareados foram escritos diretamente a partir dos registros desta rotina, antes de qualquer chamada ao Gemini. A nota `nf_013.pdf` não contém data; seu valor esperado é `null`.
