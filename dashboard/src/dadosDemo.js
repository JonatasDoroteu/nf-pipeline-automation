const dadosDemo = {
  obra_id: 1,
  etapas: [
    {
      nome: 'Preliminares',
      orcamento_planejado: 15415.69,
      gasto: 0,
      percentual: 0,
      alerta: false,
    },
    {
      nome: 'Fundação',
      orcamento_planejado: 5929.11,
      gasto: 4230,
      percentual: 4230 / 5929.11,
      alerta: false,
    },
    {
      nome: 'Estrutura',
      orcamento_planejado: 17787.33,
      gasto: 12807,
      percentual: 12807 / 17787.33,
      alerta: false,
    },
    {
      nome: 'Alvenaria',
      orcamento_planejado: 10672.4,
      gasto: 4600,
      percentual: 4600 / 10672.4,
      alerta: false,
    },
    {
      nome: 'Telhado',
      orcamento_planejado: 7114.93,
      gasto: 0,
      percentual: 0,
      alerta: false,
    },
    {
      nome: 'Hidráulica',
      orcamento_planejado: 11858.22,
      gasto: 11270,
      percentual: 11270 / 11858.22,
      alerta: true,
    },
    {
      nome: 'Elétrica',
      orcamento_planejado: 9486.58,
      gasto: 2900,
      percentual: 2900 / 9486.58,
      alerta: false,
    },
    {
      nome: 'Esquadrias',
      orcamento_planejado: 8300.75,
      gasto: 0,
      percentual: 0,
      alerta: false,
    },
    {
      nome: 'Acabamento',
      orcamento_planejado: 32017.19,
      gasto: 6000,
      percentual: 6000 / 32017.19,
      alerta: false,
    },
  ],
  sem_classificacao: {
    gasto: 1250,
  },
}

export default dadosDemo