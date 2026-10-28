import { useRef, useState } from 'react'
import dadosDemo from './dadosDemo'
import './App.css'

const moeda = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

const percentualFormatado = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

function App() {
  const [modo, setModo] = useState('demo')
  const [chaveApi, setChaveApi] = useState('')
  const [obraId, setObraId] = useState('1')
  const [dados, setDados] = useState(dadosDemo)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState('')
  const requisicaoAtual = useRef(0)
  const controllerAtual = useRef(null)
  const modoRealDisponivel = !import.meta.env.PROD

  function cancelarRequisicaoAtual() {
    requisicaoAtual.current += 1
    controllerAtual.current?.abort()
    controllerAtual.current = null
    setCarregando(false)
  }

  function selecionarDemo() {
    cancelarRequisicaoAtual()
    setModo('demo')
    setDados(dadosDemo)
    setErro('')
  }

  function selecionarReal() {
    if (!modoRealDisponivel) return

    cancelarRequisicaoAtual()
    setModo('real')
    setDados(null)
    setErro('')
  }

  async function carregarDados(event) {
    event.preventDefault()
    if (modo !== 'real' || !chaveApi.trim() || !obraId.trim()) return

    controllerAtual.current?.abort()
    const controller = new AbortController()
    controllerAtual.current = controller
    const idRequisicao = ++requisicaoAtual.current

    setCarregando(true)
    setErro('')
    setDados(null)

    try {
      const resposta = await fetch(
        `/obras/${encodeURIComponent(obraId.trim())}/resumo`,
        {
          headers: {
            'X-API-Key': chaveApi.trim(),
          },
          signal: controller.signal,
        },
      )

      if (idRequisicao !== requisicaoAtual.current) return

      if (resposta.status === 401) {
        setErro('Chave inválida')
        return
      }

      if (resposta.status === 404) {
        setErro('Obra não encontrada')
        return
      }

      if (resposta.status >= 500) {
        setErro('API fora do ar. Tente o modo demo')
        return
      }

      if (!resposta.ok) {
        setErro(`A API retornou um erro (HTTP ${resposta.status}).`)
        return
      }

      const resultado = await resposta.json()
      if (
        !resultado ||
        typeof resultado !== 'object' ||
        !Array.isArray(resultado.etapas) ||
        !resultado.sem_classificacao ||
        typeof resultado.sem_classificacao.gasto !== 'number'
      ) {
        setErro('A resposta da API não está no formato esperado.')
        return
      }

      setDados(resultado)
    } catch (erroRequisicao) {
      if (idRequisicao !== requisicaoAtual.current) return

      if (erroRequisicao instanceof TypeError) {
        setErro('API fora do ar. Tente o modo demo')
      } else if (erroRequisicao.name !== 'AbortError') {
        setErro('Não foi possível carregar os dados. Tente novamente.')
      }
    } finally {
      if (idRequisicao === requisicaoAtual.current) {
        setCarregando(false)
        controllerAtual.current = null
      }
    }
  }

  const orcamentoTotal = dados
    ? dados.etapas.reduce(
        (total, etapa) => total + etapa.orcamento_planejado,
        0,
      )
    : 0
  const gastoEtapas = dados
    ? dados.etapas.reduce((total, etapa) => total + etapa.gasto, 0)
    : 0
  const gastoTotal = gastoEtapas + (dados?.sem_classificacao.gasto ?? 0)
  const percentualTotal =
    orcamentoTotal > 0 ? (gastoTotal / orcamentoTotal) * 100 : 0
  const etapasEmAlerta = dados
    ? dados.etapas.filter((etapa) => etapa.alerta).length
    : 0

  return (
    <main className="painel">
      <header className="cabecalho">
        <div>
          <p className="sobretitulo">CONTROLE DE CUSTOS · OBRA 01</p>
          <h1>Custos da obra</h1>
          <p className="subtitulo">Obra simulada: Casa 60m²</p>
        </div>

        <div className="alternador" role="group" aria-label="Modo de dados">
          <button
            className="botao-modo"
            type="button"
            aria-pressed={modo === 'real'}
            disabled={!modoRealDisponivel}
            onClick={selecionarReal}
          >
            Real
          </button>
          <button
            className="botao-modo"
            type="button"
            aria-pressed={modo === 'demo'}
            onClick={selecionarDemo}
          >
            Demo
          </button>
        </div>
      </header>

      {modo === 'demo' ? (
        <p className="selo-demo">DADOS DE DEMONSTRAÇÃO</p>
      ) : (
        <form id="form-real" className="form-real" onSubmit={carregarDados}>
          <div className="campo">
            <label htmlFor="obra-id">ID da obra</label>
            <input
              id="obra-id"
              type="number"
              min="1"
              step="1"
              value={obraId}
              onChange={(event) => setObraId(event.target.value)}
              required
            />
          </div>
          <div className="campo campo-chave">
            <label htmlFor="chave-api">Chave da API</label>
            <input
              id="chave-api"
              type="password"
              autoComplete="off"
              value={chaveApi}
              onChange={(event) => setChaveApi(event.target.value)}
              required
            />
          </div>
          <small className="dica-chave">
            A chave fica apenas enquanto esta aba estiver aberta.
          </small>
          <button
            className="botao-principal"
            type="submit"
            disabled={!chaveApi.trim() || !obraId.trim() || carregando}
          >
            Carregar dados reais
          </button>
        </form>
      )}

      <p
        className={`status${erro ? ' status-erro' : ''}`}
        role="status"
        aria-live="polite"
      >
        {carregando ? 'Carregando...' : erro}
      </p>

      {erro && modo === 'real' && (
        <button
          className="botao-secundario"
          type="submit"
          form="form-real"
          disabled={!chaveApi.trim() || !obraId.trim() || carregando}
        >
          Tentar de novo
        </button>
      )}

      {dados && (
        <>
          <section className="resumo" aria-label="Resumo financeiro">
            <div className="indicador">
              <span className="rotulo">Orçamento total</span>
              <strong className="numero">{moeda.format(orcamentoTotal)}</strong>
            </div>
            <div className="indicador">
              <span className="rotulo">Gasto total</span>
              <strong className="numero">{moeda.format(gastoTotal)}</strong>
            </div>
            <div className="indicador">
              <span className="rotulo">% gasto</span>
              <strong className="numero">
                {percentualFormatado.format(percentualTotal)}%
              </strong>
            </div>
            <div className="indicador">
              <span className="rotulo">Etapas em alerta</span>
              <strong className="numero">{etapasEmAlerta}</strong>
            </div>
          </section>

          <section className="secao-etapas" aria-labelledby="titulo-etapas">
            <div className="titulo-secao">
              <h2 id="titulo-etapas">Etapas da obra</h2>
              <span>Gasto em relação ao orçamento planejado</span>
            </div>

            <div className="cabecalho-tabela" aria-hidden="true">
              <span>Etapa</span>
              <span>Progresso</span>
              <span>Gasto / orçamento</span>
              <span>%</span>
            </div>

            <ul className="lista-etapas">
              {dados.etapas.map((etapa) => {
                const percentual =
                  etapa.orcamento_planejado > 0
                    ? etapa.percentual * 100
                    : null
                const alerta = etapa.alerta || (percentual ?? 0) >= 90
                const larguraBarra = Math.min(
                  Math.max(percentual ?? 0, 0),
                  100,
                )

                return (
                  <li
                    className={`linha-etapa${alerta ? ' em-alerta' : ''}`}
                    key={etapa.nome}
                  >
                    <span className="nome-etapa">{etapa.nome}</span>
                    <span
                      className="trilho-progresso"
                      role="progressbar"
                      aria-label={`Gasto de ${etapa.nome}`}
                      aria-valuemin="0"
                      aria-valuemax="100"
                      aria-valuenow={larguraBarra}
                      aria-valuetext={
                        percentual === null
                          ? 'Orçamento não definido'
                          : `${percentualFormatado.format(percentual)}% do orçamento`
                      }
                    >
                      <span
                        className="barra-progresso"
                        style={{ width: `${larguraBarra}%` }}
                      />
                    </span>
                    <span className="valores-etapa numero">
                      <span>{moeda.format(etapa.gasto)}</span>
                      <span className="separador-valores">/</span>
                      <span>{moeda.format(etapa.orcamento_planejado)}</span>
                    </span>
                    <span className="percentual-etapa numero">
                      {percentual === null
                        ? '—'
                        : `${percentualFormatado.format(percentual)}%`}
                      {alerta && <span className="selo-alerta">ALERTA</span>}
                    </span>
                  </li>
                )
              })}
            </ul>
          </section>

          <section className="linha-sem-classificacao">
            <span>Sem classificação</span>
            <strong className="numero">
              {moeda.format(dados.sem_classificacao.gasto)}
            </strong>
          </section>
        </>
      )}

      <footer className="rodape">
        <span>NF Pipeline</span>
        <span>Casa 60m² · acompanhamento de custos</span>
      </footer>
    </main>
  )
}

export default App
