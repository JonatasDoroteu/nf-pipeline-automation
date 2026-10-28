import { useRef, useState } from 'react'
import dadosDemo from './dadosDemo'

function App() {
  const [modo, setModo] = useState('demo')
  const [chaveApi, setChaveApi] = useState('')
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
    if (modo !== 'real' || !chaveApi.trim()) return

    controllerAtual.current?.abort()
    const controller = new AbortController()
    controllerAtual.current = controller
    const idRequisicao = ++requisicaoAtual.current

    setCarregando(true)
    setErro('')
    setDados(null)

    try {
      const resposta = await fetch('/obras/1/resumo', {
        headers: {
          'X-API-Key': chaveApi.trim(),
        },
        signal: controller.signal,
      })

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

  return (
    <main>
      <header>
        <h1>Custos da obra</h1>
        <p>Obra simulada: Casa 60m²</p>

        <div aria-label="Modo de dados">
          <button
            type="button"
            aria-pressed={modo === 'real'}
            disabled={!modoRealDisponivel}
            onClick={selecionarReal}
          >
            Real
          </button>
          <button
            type="button"
            aria-pressed={modo === 'demo'}
            onClick={selecionarDemo}
          >
            Demo
          </button>
        </div>
      </header>

      {modo === 'demo' ? (
        <p>DADOS DE DEMONSTRAÇÃO</p>
      ) : (
        <form onSubmit={carregarDados}>
          <label htmlFor="chave-api">Chave da API</label>
          <input
            id="chave-api"
            type="password"
            autoComplete="off"
            value={chaveApi}
            onChange={(event) => setChaveApi(event.target.value)}
          />
          <small>A chave fica apenas enquanto esta aba estiver aberta.</small>
          <button type="submit" disabled={!chaveApi.trim() || carregando}>
            Carregar dados reais
          </button>
        </form>
      )}

      <p role="status" aria-live="polite">
        {carregando
          ? 'Carregando...'
          : erro ||
            (modo === 'real' && !dados
              ? 'Informe a chave da API para carregar os dados.'
              : '')}
      </p>

      {erro && modo === 'real' && (
        <button type="button" onClick={carregarDados}>
          Tentar de novo
        </button>
      )}

      {dados && (
        <>
          <section>
            <h2>Etapas</h2>
            <ul>
              {dados.etapas.map((etapa) => (
                <li key={etapa.nome}>
                  {etapa.nome}: R$ {etapa.gasto.toFixed(2)} / R${' '}
                  {etapa.orcamento_planejado.toFixed(2)} —{' '}
                  {(etapa.percentual * 100).toFixed(1)}%
                  {etapa.alerta ? ' — ALERTA' : ''}
                </li>
              ))}
            </ul>
          </section>

          <p>
            Sem classificação: R${' '}
            {dados.sem_classificacao.gasto.toFixed(2)}
          </p>
        </>
      )}
    </main>
  )
}

export default App
