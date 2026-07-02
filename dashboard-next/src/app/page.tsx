'use client'

import { useEffect, useState, useRef } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts'
import { HintTooltip } from '@/components/HintTooltip'
import { RealityPanel } from '@/components/RealityPanel'

interface Config {
  goal: number; goalDays: number; capitalInitial: number
  minTrade: number; maxTrade: number; dryRun: boolean; autoExecute?: boolean
  takeProfit?: number; stopLoss?: number; trailingStop?: number
  reserveFloor?: number; maxDailyExposure?: number
}

interface AgentInfo {
  status: 'active' | 'idle' | 'recent' | 'offline'
  mode: 'daemon' | 'cycle'
  lastRun: string | null
}

function formatLastActive(info?: AgentInfo): string {
  if (!info) return 'nunca'
  if (info.mode === 'daemon' && info.status === 'active') return 'daemon ativo'
  if (!info.lastRun) return info.status === 'offline' ? 'offline' : '—'
  const d = new Date(info.lastRun)
  const agoMin = Math.round((Date.now() - d.getTime()) / 60000)
  if (agoMin < 1) return 'agora'
  if (agoMin < 60) return `${agoMin}min atrás`
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export default function DashboardPage() {
  const [data, setData] = useState<any>(null)
  const [config, setConfig] = useState<Config | null>(null)
  const [recs, setRecs] = useState<any>(null)
  const [botData, setBotData] = useState<any>(null)
  const [agentStatus, setAgentStatus] = useState<Record<string, string>>({})
  const [agentInfo, setAgentInfo] = useState<Record<string, AgentInfo>>({})
  const feedRef = useRef<HTMLDivElement>(null)

  const [processingSync, setProcessingSync] = useState(false)
  const [opsRunning, setOpsRunning] = useState<string | null>(null)
  const [agentAction, setAgentAction] = useState<string | null>(null)
  const [loopStatus, setLoopStatus] = useState<any>(null)
  const [loopAction, setLoopAction] = useState<'start' | 'stop' | null>(null)

  const toggleAgent = async (agentName: string) => {
    const info = agentInfo[agentName]
    const isCycle = info?.mode === 'cycle'
    const isDaemonRunning = !isCycle && info?.status === 'active'
    const action = isDaemonRunning ? 'stop' : 'start'
    setAgentAction(agentName)
    try {
      const res = await fetch('/api/agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent: agentName, action })
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(body.error || 'Falha ao iniciar agente')
      setTimeout(fetchAll, isCycle ? 3000 : 2000)
    } catch (e) {
      console.error(e)
      alert(`Erro ao ${action === 'start' ? 'iniciar' : 'parar'} ${agentName}: ${e instanceof Error ? e.message : 'erro desconhecido'}`)
      fetchAll()
    } finally {
      setAgentAction(null)
    }
  }

  const runOp = async (action: string, endpoint = '/api/ops') => {
    setOpsRunning(action)
    try {
      if (action === 'run-cycle') {
        const res = await fetch('/api/agents/run-cycle', { method: 'POST' })
        const body = await res.json().catch(() => ({}))
        if (!res.ok) {
          alert(body.error || 'Ciclo em andamento — aguarde o ciclo atual terminar.')
        }
      } else {
        await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action }),
        })
      }
      setTimeout(fetchAll, 2500)
    } finally {
      setOpsRunning(null)
    }
  }

  const fetchAll = async (manual = false) => {
    if (manual) setProcessingSync(true)
    try {
      const [resData, resConfig, resRecs, resAgents, resBots, resLoop] = await Promise.all([
        fetch('/api/data?type=summary').then(r => r.json()).catch(() => null),
        fetch('/api/config').then(r => r.json()).catch(() => null),
        fetch('/api/recommendations?limit=50').then(r => r.json()).catch(() => null),
        fetch('/api/agents').then(r => r.json()).catch(() => null),
        fetch('/api/bots').then(r => r.json()).catch(() => null),
        fetch('/api/loop/status').then(r => r.json()).catch(() => null),
      ])
      if (resData) setData(resData)
      if (resConfig) setConfig(resConfig)
      if (resRecs) setRecs(resRecs)
      if (resAgents?.agents) setAgentInfo(resAgents.agents)
      if (resAgents?.statuses) setAgentStatus(resAgents.statuses)
      if (resBots) setBotData(resBots)
      if (resLoop) setLoopStatus(resLoop)
    } finally {
      if (manual) setProcessingSync(false)
    }
  }

  useEffect(() => {
    fetchAll(false)
    const tick = () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
      fetchAll(false)
    }
    const interval = setInterval(tick, 10000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = 0
  }, [data])

  const stats = data?.executions?.stats
  const balance = data?.balance
  const health = data?.health
  const positions = data?.positions
  const goal = config?.goal || 10000
  const goalDays = config?.goalDays || 30
  const capitalInitial = config?.capitalInitial || 9
  const balanceUsd = balance?.usdc ?? 0

  const portfolioValue = positions?.portfolioValue || 0
  const totalEquity = balanceUsd + portfolioValue
  const pnl = totalEquity > 0 ? totalEquity - capitalInitial : (stats?.totalPnl || 0)

  const progress = Math.min((totalEquity / goal) * 100, 100)
  const winRate = stats?.total > 0 ? Math.round((stats.success / stats.total) * 100) : 0
  const executorOnline = !health?.offline
  const feedItems = (data?.executions?.data || []).slice().reverse()

  const toggleLoop = async (action: 'start' | 'stop') => {
    setLoopAction(action)
    try {
      await fetch(`/api/loop/${action}`, { method: 'POST' })
      setTimeout(fetchAll, 2000)
    } finally {
      setLoopAction(null)
    }
  }

  const latestBot = botData?.analyses?.[0]

  return (
    <div className="space-y-5 max-w-[1400px]">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">🦞 PolyClaw Dashboard</h1>
          <p className="text-sm text-muted mt-1">Painel operacional — Polymarket Trading</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={() => fetchAll(true)}
            disabled={processingSync}
            className={`px-4 py-2 rounded-lg text-sm font-bold border transition-colors flex items-center gap-2 ${processingSync ? 'bg-blue-500/20 text-blue-400 border-blue-500/40 cursor-wait' : 'bg-blue-600 text-white border-blue-500 hover:bg-blue-500 shadow-lg shadow-blue-500/20'}`}
          >
            {processingSync ? '🔄 Atualizando...' : '🔄 Atualizar dados'}
            <HintTooltip hint="Busca saldo USDC, posições abertas e histórico de execuções do executor na porta 8789." />
          </button>

          <span className={`badge ${executorOnline ? 'badge-success' : 'badge-danger'} flex items-center gap-1`}>
            {executorOnline ? '● Executor Online' : '● Executor Offline'}
            <HintTooltip hint="API que envia ordens reais ao Polymarket CLOB. Offline = sem saldo/posições no painel." />
          </span>
          <span className={`badge ${health?.dry_run ? 'badge-warning' : 'badge-success'} flex items-center gap-1`}>
            {health?.dry_run ? '🧪 Simulação' : '🔴 Live'}
            <HintTooltip
              hint="Live = ordens reais com USDC. Simulação = registra trades sem gastar dinheiro."
              danger={!health?.dry_run}
            />
          </span>
          <span className="text-xs text-muted font-mono">
            {new Date().toLocaleString('pt-BR')}
          </span>
        </div>
      </div>

      {config && !config.dryRun && (
        <div className="glass-card px-4 py-3 border border-red-500/30 bg-red-500/5 flex items-center gap-3 flex-wrap">
          <span className="text-red-300 font-semibold text-sm">🔴 Modo Live ativo</span>
          <span className="text-xs text-muted">
            Máx ${config.maxTrade}/trade · Máx ${config.maxDailyExposure ?? 10}/dia · Reserva ${config.reserveFloor ?? 6} USDC
            {config.autoExecute
              ? ' · ⚠️ autoExecute ligado'
              : ' · Aprovação manual obrigatória'}
          </span>
        </div>
      )}

      {!executorOnline && (
        <div className="glass-card px-4 py-3 border border-amber-500/30 bg-amber-500/5 flex items-center justify-between gap-3 flex-wrap">
          <span className="text-amber-300 text-sm">
            ⚠️ Executor offline — saldo, posições e trades ao vivo não aparecem.
          </span>
          <button
            onClick={() => toggleAgent('Executor')}
            disabled={agentAction === 'Executor'}
            className="px-3 py-1.5 rounded-lg text-xs font-bold bg-amber-600 text-white hover:bg-amber-500 disabled:opacity-50"
          >
            {agentAction === 'Executor' ? 'Iniciando...' : 'Iniciar Executor'}
          </button>
        </div>
      )}

      <RealityPanel variant="compact" showActivateReal={false} />

      {/* Operações Rápidas */}
      <div className="glass-card p-4">
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          ⚡ Operações Rápidas
          <HintTooltip hint="Ações de um clique para rodar agentes e processar trades sem usar o terminal." />
        </h3>
        <div className="flex flex-wrap gap-2">
          <QuickOpBtn
            label="Executar ciclo completo"
            action="run-cycle"
            running={opsRunning}
            onRun={runOp}
            hint="Roda smart-cycle: preflight → análise → decisão → execução → recovery → observabilidade."
          />
          <QuickOpBtn
            label="Processar aprovados"
            action="process-recs"
            running={opsRunning}
            onRun={runOp}
            hint="Envia ao Polymarket todas as recomendações que você já aceitou no dashboard."
            skill="polymarket-exec"
          />
          <QuickOpBtn
            label="Analisar bots"
            action="analyze-bots"
            running={opsRunning}
            onRun={runOp}
            hint="Estuda wallets da watchlist e classifica estratégias (Rotation, Temporal Arb, MM, etc.)."
            skill="polybot-analyzer"
          />
          <QuickOpBtn
            label="Calibrar minEdge"
            action="calibrate-edge"
            running={opsRunning}
            onRun={runOp}
            hint="Ajusta o edge mínimo em Configurações com base na análise dos bots lucrativos."
            skill="polybot-analyzer"
          />
          <QuickOpBtn
            label="Verificar latência"
            action="check-latency"
            running={opsRunning}
            onRun={runOp}
            hint="Testa velocidade da Gamma API, executor e Redis. Target: <3s."
            skill="latencyninja"
          />
        </div>
      </div>

      {/* Smart Loop Status */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            🧠 Smart Loop
            <HintTooltip hint="Orquestrador 24/7 com fases, lock anti-overlap e intervalo dinâmico. Complementado pelo supervisor Cursor (/loop skills/agent-loop)." />
          </h3>
          <div className="flex items-center gap-2">
            {loopStatus?.smartLoop?.running ? (
              <button
                onClick={() => toggleLoop('stop')}
                disabled={!!loopAction}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 disabled:opacity-50"
              >
                {loopAction === 'stop' ? 'Parando...' : '⏹ Parar Loop'}
              </button>
            ) : (
              <button
                onClick={() => toggleLoop('start')}
                disabled={!!loopAction}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-green-500/20 text-green-400 border border-green-500/30 hover:bg-green-500/30 disabled:opacity-50"
              >
                {loopAction === 'start' ? 'Iniciando...' : '▶ Iniciar Loop'}
              </button>
            )}
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <div>
            <span className="text-muted">Status</span>
            <div className={`font-semibold mt-0.5 ${loopStatus?.smartLoop?.running ? 'text-green-400' : 'text-muted'}`}>
              {loopStatus?.smartLoop?.running ? '● Rodando' : '○ Parado'}
              {loopStatus?.lock?.held && ' · Ciclo ativo'}
            </div>
          </div>
          <div>
            <span className="text-muted">Ciclo #</span>
            <div className="text-white font-mono mt-0.5">{loopStatus?.state?.cycleNumber ?? 0}</div>
          </div>
          <div>
            <span className="text-muted">Próximo run</span>
            <div className="text-white font-mono mt-0.5">
              {loopStatus?.state?.nextRunAt
                ? new Date(loopStatus.state.nextRunAt).toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit' })
                : '—'}
            </div>
          </div>
          <div>
            <span className="text-muted">Intervalo</span>
            <div className="text-white font-mono mt-0.5">
              {loopStatus?.state?.intervalUsed
                ? `${Math.round(loopStatus.state.intervalUsed / 60)} min`
                : loopStatus?.config?.intervalSeconds
                  ? `${Math.round(loopStatus.config.intervalSeconds / 60)} min`
                  : '15 min'}
            </div>
          </div>
        </div>
        {loopStatus?.state?.phases?.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {loopStatus.state.phases.map((p: { name: string; status: string }) => (
              <span
                key={p.name}
                className={`badge text-[9px] ${p.status === 'ok' ? 'badge-success' : 'badge-danger'}`}
              >
                {p.name}
              </span>
            ))}
          </div>
        )}
        {loopStatus?.state?.errors?.length > 0 && (
          <div className="mt-2 text-[10px] text-red-400">
            {loopStatus.state.errors.length} erro(s) no último ciclo
          </div>
        )}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <KpiCard label="Cash USDC" value={`$${balanceUsd.toFixed(2)}`}
          sub={balance?.address ? `${balance.address.substring(0, 8)}...` : 'wallet'}
          icon="💰" color="blue"
          hint="Saldo livre na carteira Polymarket (proxy wallet). Não inclui valor de posições abertas." />
        <KpiCard label="PnL Total" value={`${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`}
          sub={`Ativos: $${portfolioValue.toFixed(2)}`}
          icon={pnl >= 0 ? '📈' : '📉'} color={pnl >= 0 ? 'green' : 'red'}
          hint="Lucro/prejuízo = (cash + valor posições) − capital inicial configurado." />
        <KpiCard label="Meta" value={`$${goal.toLocaleString()}`}
          sub={`${progress.toFixed(1)}% • ${goalDays}d`}
          icon="🎯" color="purple" progress={progress}
          hint="Objetivo de capital total. Barra mostra progresso atual." />
        <KpiCard label="Win Rate" value={`${winRate}%`}
          sub={`${stats?.success || 0}W / ${stats?.errors || 0}L`}
          icon="🏆" color={winRate >= 60 ? 'green' : winRate >= 40 ? 'amber' : 'red'}
          hint="Taxa de execuções bem-sucedidas vs falhas em executions.jsonl." />
        <KpiCard label="Trades Total" value={stats?.total?.toString() || '0'}
          sub={`${stats?.live || 0} live • ${stats?.dryRun || 0} dry`}
          icon="⚡" color="blue"
          hint="Todas as tentativas: live, dry-run e aceites manuais." />
        <KpiCard label="Recs Pendentes" value={recs?.stats?.pending?.toString() || '0'}
          sub={`${recs?.stats?.executed || 0} exec • ${recs?.stats?.rejected || 0} rej`}
          icon="🎯" color="amber"
          hint="Recomendações do PolyWhale aguardando sua aprovação manual." />
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-white mb-3">📈 Projeção ${capitalInitial} → ${goal.toLocaleString()}</h3>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={generateGrowthData(capitalInitial, goal, goalDays)}>
                <defs>
                  <linearGradient id="colorBal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e2d3d" />
                <XAxis dataKey="day" stroke="#64748b" fontSize={10} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={10} tickLine={false} tickFormatter={v => `$${v}`} />
                <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1e2d3d', borderRadius: 8 }}
                  formatter={(v: number) => [`$${v.toFixed(0)}`, '']} />
                <Area type="monotone" dataKey="target" stroke="#64748b" strokeDasharray="5 5" fill="none" name="Linear" />
                <Area type="monotone" dataKey="projected" stroke="#3b82f6" fill="url(#colorBal)" strokeWidth={2} name="Projetado" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              🤖 Agentes em Atividade
              <HintTooltip hint="Cada agente corresponde a um skill do OpenClaw. Use o toggle para iniciar/parar processos." />
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <AgentDetail name="PolyClaw" agentId="PolyClaw" role="Paper Trading" skill="polyclaw"
                status={agentInfo['PolyClaw']?.status || 'offline'}
                mode={agentInfo['PolyClaw']?.mode}
                busy={agentAction === 'PolyClaw'}
                details={[`${data?.simulated?.total || 0} mercados simulados`, 'Gamma API + edge simulado', 'Nunca gasta USDC real']}
                onToggle={() => toggleAgent('PolyClaw')}
                toggleHint="Gera paper trades em simulated_trades.jsonl."
                model="gamma-scanner" lastActive={formatLastActive(agentInfo['PolyClaw'])} />
              <AgentDetail name="PolyWhale" agentId="PolyWhale" role="Strategy & Recommendations" skill="polywhale"
                status={agentInfo['PolyWhale']?.status || 'offline'}
                mode={agentInfo['PolyWhale']?.mode}
                busy={agentAction === 'PolyWhale'}
                details={[`${recs?.stats?.total || 0} recomendações`, 'Arb, mispricing, carry, weather', 'Análise de edge e confiança']}
                onToggle={() => toggleAgent('PolyWhale')}
                toggleHint="Analisa mercados e escreve recommendations.jsonl."
                model="gemini-flash" lastActive={formatLastActive(agentInfo['PolyWhale'])} />
              <AgentDetail name="Polybot Analyzer" agentId="Polybot" role="Bot Intelligence" skill="polybot-analyzer"
                status={agentInfo['Polybot']?.status || 'offline'}
                mode={agentInfo['Polybot']?.mode}
                busy={agentAction === 'Polybot'}
                details={[
                  latestBot ? `Última: ${latestBot.strategy}` : 'Sem análise recente',
                  `${botData?.stats?.wallets || 0} wallets na watchlist`,
                  'Ver detalhes em /bots',
                ]}
                onToggle={() => toggleAgent('Polybot')}
                toggleHint="Classifica estratégias de bots concorrentes via data-api."
                model="bayes+kelly" lastActive={formatLastActive(agentInfo['Polybot'])} />
              <AgentDetail name="Brimo" agentId="Brimo" role="Sell Specialist" skill="polymarket-exec"
                status={agentInfo['Brimo']?.status || 'offline'}
                mode={agentInfo['Brimo']?.mode}
                busy={agentAction === 'Brimo'}
                details={[
                  `TP: ${config?.takeProfit ?? 20}% | SL: ${config?.stopLoss ?? 15}%`,
                  `Reserve Floor: $${config?.reserveFloor ?? 3}`,
                  `Trailing: ${config?.trailingStop ?? 10}% do pico`,
                ]}
                onToggle={() => toggleAgent('Brimo')}
                toggleHint="Monitora posições (--monitor, ciclo 60s) e vende em TP/SL."
                model="position-monitor" lastActive={formatLastActive(agentInfo['Brimo'])} />
              <AgentDetail name="Executor" agentId="Executor" role="Trade Execution" skill="polymarket-exec"
                status={agentInfo['Executor']?.status || 'offline'}
                mode={agentInfo['Executor']?.mode}
                busy={agentAction === 'Executor'}
                details={[
                  `Modo: ${health?.dry_run ? 'SIMULAÇÃO' : 'LIVE'}`,
                  `Max trade: $${health?.max_trade_usd || config?.maxTrade || '?'}`,
                  `Falhas consec.: ${health?.consecutive_failures || 0}`,
                ]}
                onToggle={() => toggleAgent('Executor')}
                toggleHint="API CLOB na porta 8789 — executa ordens aprovadas."
                model="py-clob-client" lastActive={formatLastActive(agentInfo['Executor'])} />
              <AgentDetail name="LatencyNinja" role="Health & Latency" skill="latencyninja"
                status={agentInfo['LatencyNinja']?.status || 'offline'}
                mode={agentInfo['LatencyNinja']?.mode}
                details={['Gamma API, executor, Redis', 'Target latência <3s', 'Use Verificar latência acima']}
                model="hft-profiler" lastActive={formatLastActive(agentInfo['LatencyNinja'])} />
              <AgentDetail name="CorrectionAgent" agentId="CorrectionAgent" role="Auto-Fix Daemon"
                status={agentInfo['CorrectionAgent']?.status || 'offline'}
                mode={agentInfo['CorrectionAgent']?.mode}
                busy={agentAction === 'CorrectionAgent'}
                details={['Aplica correções aprovadas', 'Escuta /api/corrections', 'Ver /error-analysis']}
                onToggle={() => toggleAgent('CorrectionAgent')}
                toggleHint="Daemon que aplica fixes após aprovação no dashboard."
                model="direct terminal" lastActive={formatLastActive(agentInfo['CorrectionAgent'])} />
              <AgentDetail name="AutoCorrect" agentId="AutoCorrect" role="Error Scanner"
                status={agentInfo['AutoCorrect']?.status || 'offline'}
                mode={agentInfo['AutoCorrect']?.mode}
                busy={agentAction === 'AutoCorrect'}
                details={['Escaneia erros de execução', 'Propõe fixes em corrections.jsonl', 'Ver /error-analysis']}
                onToggle={() => toggleAgent('AutoCorrect')}
                toggleHint="Analisa falhas e sugere correções automáticas."
                model="error-analyzer" lastActive={formatLastActive(agentInfo['AutoCorrect'])} />
            </div>
          </div>
        </div>

        <div className="glass-card p-4 flex flex-col" style={{ maxHeight: 540 }}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              📜 Live Trade Feed
              <HintTooltip hint="Stream das últimas ações: aceites, execuções live, dry-runs e erros." />
            </h3>
            <span className="text-[10px] text-muted font-mono">auto-refresh 10s</span>
          </div>
          <div ref={feedRef} className="flex-1 overflow-y-auto space-y-2 pr-1" style={{ maxHeight: 470 }}>
            {feedItems.length === 0 && (
              <div className="text-center text-muted text-sm py-8">Aguardando trades...</div>
            )}
            {feedItems.map((exec: any, i: number) => (
              <FeedItem key={i} exec={exec} />
            ))}
          </div>
        </div>
      </div>

      {recs?.recommendations?.filter((r: any) => ['accepted', 'failed'].includes(r._status)).length > 0 && (
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-white mb-3">📋 Aprovações recentes</h3>
          <div className="space-y-2">
            {recs.recommendations.filter((r: any) => ['accepted', 'failed'].includes(r._status)).slice(0, 5).map((rec: any) => (
              <RecCard key={rec._id} rec={rec} onAction={fetchAll} />
            ))}
          </div>
        </div>
      )}

      {recs?.recommendations?.filter((r: any) => r._status === 'pending').length > 0 && (
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            🎯 Recomendações Pendentes
            <span className="badge badge-warning">{recs.stats.pending}</span>
            <HintTooltip skill="polywhale" hint="Sugestões do PolyWhale aguardando sua decisão. Aprovar dispara execução imediata." />
          </h3>
          <div className="space-y-2">
            {recs.recommendations.filter((r: any) => r._status === 'pending').slice(0, 5).map((rec: any) => (
              <RecCard key={rec._id} rec={rec} onAction={fetchAll} />
            ))}
          </div>
        </div>
      )}

      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          📊 Posições Ativas
          {positions?.offline && <span className="ml-2 badge badge-danger">Offline</span>}
          <HintTooltip hint="Mercados onde você tem dinheiro em jogo. PnL = diferença entre preço atual e entrada." />
        </h3>
        {positions?.positions && positions.positions.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr><th>Market</th><th>Side</th><th>Size</th><th>Entry Price</th><th>Current</th><th>PnL</th></tr>
            </thead>
            <tbody>
              {positions.positions.map((p: any, i: number) => (
                <tr key={i}>
                  <td className="text-xs font-mono text-accent">{p.market?.substring(0, 16)}...</td>
                  <td><span className="badge badge-success">{p.outcome || p.side}</span></td>
                  <td className="font-mono text-xs">${p.size || p.amount || '?'}</td>
                  <td className="font-mono text-xs">{p.avgPrice?.toFixed(3) || '?'}</td>
                  <td className="font-mono text-xs">{p.currentPrice?.toFixed(3) || '?'}</td>
                  <td className={`font-mono text-xs ${(p.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {p.pnl !== undefined ? `$${p.pnl.toFixed(2)}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="text-center text-muted text-sm py-6">
            {positions?.offline
              ? 'Executor offline — bash scripts/start-executor.sh'
              : 'Sem posições ativas no momento'}
          </div>
        )}
      </div>
    </div>
  )
}

function QuickOpBtn({ label, action, running, onRun, hint, skill }: {
  label: string; action: string; running: string | null
  onRun: (a: string) => void; hint: string; skill?: string
}) {
  const busy = running === action
  return (
    <button
      onClick={() => onRun(action)}
      disabled={!!running}
      className="px-3 py-2 rounded-lg text-xs font-semibold bg-surface-2 border border-border hover:border-accent/40 text-white disabled:opacity-50 flex items-center gap-1.5"
    >
      {busy ? '⏳' : '▶'} {label}
      <HintTooltip hint={hint} skill={skill} />
    </button>
  )
}

function generateGrowthData(start: number, target: number, days: number) {
  return Array.from({ length: days }, (_, i) => ({
    day: i + 1,
    target: start + ((target - start) / days) * (i + 1),
    projected: start + (target - start) * (1 - Math.exp(-(i + 1) / (days * 0.4))) * (1 + Math.sin(i / 4) * 0.03),
  }))
}

function KpiCard({ label, value, sub, icon, color, progress, hint }: {
  label: string; value: string; sub: string; icon: string; color: string; progress?: number; hint?: string
}) {
  const gradients: Record<string, string> = {
    blue: 'from-blue-500/10 to-indigo-500/5',
    purple: 'from-purple-500/10 to-pink-500/5',
    green: 'from-emerald-500/10 to-teal-500/5',
    amber: 'from-amber-500/10 to-orange-500/5',
    red: 'from-red-500/10 to-rose-500/5',
  }
  return (
    <div className={`glass-card kpi-glow p-4 bg-gradient-to-br ${gradients[color] || gradients.blue}`}>
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] text-muted font-medium uppercase tracking-wide flex items-center gap-1">
            {label}
            {hint && <HintTooltip hint={hint} />}
          </span>
          <span className="text-lg">{icon}</span>
        </div>
        <div className="text-xl font-bold text-white font-mono">{value}</div>
        <div className="text-[10px] text-muted mt-0.5">{sub}</div>
        {progress !== undefined && (
          <div className="progress-bar mt-2">
            <div className="progress-bar-fill" style={{ width: `${Math.min(progress, 100)}%` }} />
          </div>
        )}
      </div>
    </div>
  )
}

function AgentDetail({ name, agentId, role, status, mode, details, model, lastActive, onToggle, toggleHint, skill, busy }: {
  name: string; agentId?: string; role: string
  status: 'active' | 'idle' | 'recent' | 'offline' | string
  mode?: 'daemon' | 'cycle'
  details: string[]; model: string; lastActive: string
  onToggle?: () => void; toggleHint?: string; skill?: string; busy?: boolean
}) {
  const isDaemon = mode === 'daemon'
  const isToggleOn = isDaemon ? status === 'active' : status === 'recent'
  const statusLabels: Record<string, string> = {
    active: 'ATIVO', recent: 'RECENTE', idle: 'OCIOSO', offline: 'OFFLINE',
  }
  const colors: Record<string, string> = {
    active: 'badge-success', recent: 'badge-info', idle: 'badge-warning', offline: 'badge-danger',
  }
  return (
    <div className="glass-card p-4 border border-border/50">
      <div className="flex items-center justify-between mb-2">
        <div>
          <span className="font-semibold text-sm text-white">{name}</span>
          {skill && <span className="text-[9px] text-accent ml-1 font-mono">[{skill}]</span>}
          <span className="text-xs text-muted ml-2">{role}</span>
        </div>
        <div className="flex items-center gap-2">
          {onToggle && agentId && (
            <button
              onClick={onToggle}
              disabled={busy}
              title={
                busy ? 'Iniciando...' :
                isDaemon
                  ? (isToggleOn ? 'Parar daemon' : 'Iniciar daemon')
                  : 'Executar um ciclo agora'
              }
              className={`relative inline-flex h-4 w-8 items-center rounded-full transition-colors focus:outline-none disabled:opacity-50 ${isToggleOn ? 'bg-success' : 'bg-surface-2 border border-border'}`}
            >
              <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${isToggleOn ? 'translate-x-4' : 'translate-x-0.5'}`} />
            </button>
          )}
          {toggleHint && <HintTooltip hint={toggleHint} skill={skill} />}
          {mode && (
            <span className="badge badge-muted text-[9px]">{mode === 'daemon' ? 'Daemon' : 'Ciclo'}</span>
          )}
          <span className={`badge ${colors[status] || 'badge-muted'}`}>
            {busy ? '...' : (statusLabels[status] || status.toUpperCase())}
          </span>
        </div>
      </div>
      <ul className="space-y-1 mb-2">
        {details.map((d, i) => (
          <li key={i} className="text-[11px] text-muted flex items-start gap-1.5">
            <span className="text-accent mt-0.5">›</span> {d}
          </li>
        ))}
      </ul>
      <div className="flex items-center justify-between text-[10px] text-muted border-t border-border/30 pt-2">
        <span>🧠 {model}</span>
        <span>⏱️ {lastActive}</span>
      </div>
    </div>
  )
}

function FeedItem({ exec }: { exec: any }) {
  const isSuccess = exec.success
  const isDry = exec.action?.includes('dry-run')
  const isAccepted = exec.action?.includes('accepted')
  const time = new Date(exec.timestamp).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  return (
    <div className={`rounded-lg px-3 py-2 border-l-2 ${
      isAccepted ? 'border-blue-400 bg-blue-500/5' :
      isSuccess ? (isDry ? 'border-amber-400 bg-amber-500/5' : 'border-green-400 bg-green-500/5') :
      'border-red-400 bg-red-500/5'
    }`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-muted">{time}</span>
          <span className={`badge text-[9px] ${
            isAccepted ? 'badge-info' :
            isSuccess ? (isDry ? 'badge-warning' : 'badge-success') : 'badge-danger'
          }`}>
            {isAccepted ? 'ACCEPTED' : isSuccess ? (isDry ? 'DRY' : 'LIVE') : 'FAIL'}
          </span>
        </div>
        <span className="text-[10px] text-muted">{exec.action?.replace(/_/g, ' ').substring(0, 30)}</span>
      </div>
      <div className="flex items-center justify-between mt-1">
        <span className="text-xs text-accent font-mono">
          {exec.details?.description?.substring(0, 35) || exec.details?.marketId?.substring(0, 14) || '—'}...
        </span>
        {exec.details?.sizeUsd && (
          <span className="text-xs font-mono text-white">${exec.details.sizeUsd?.toFixed(2)}</span>
        )}
      </div>
      {exec.error && <div className="text-[10px] text-red-400 mt-1 truncate">{exec.error.substring(0, 60)}</div>}
    </div>
  )
}

function RecCard({ rec, onAction }: { rec: any; onAction: () => void }) {
  const handleAction = async (action: string) => {
    await fetch('/api/recommendations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: rec._id, action }),
    })
    onAction()
  }

  const statusBadge = (() => {
    if (rec._status === 'executed') return <span className="badge badge-success">Executada</span>
    if (rec._status === 'failed') return <span className="badge badge-danger">Falhou</span>
    if (rec._status === 'accepted') return <span className="badge badge-info">Enviada ao executor</span>
    if (rec._status === 'rejected') return <span className="badge badge-muted">Descartada</span>
    return <span className="badge badge-warning">Pendente</span>
  })()

  const isPending = rec._status === 'pending'

  return (
    <div className="glass-card p-3 flex items-center justify-between gap-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          {statusBadge}
          <span className={`badge ${rec.decision?.includes('BUY') ? 'badge-success' : 'badge-muted'}`}>
            {rec.decision}
          </span>
          <span className={`badge ${rec.confidence === 'HIGH' ? 'badge-success' : rec.confidence === 'MEDIUM' ? 'badge-warning' : 'badge-muted'}`}>
            {rec.confidence}
          </span>
          {rec.edge && <span className="text-[10px] text-muted font-mono">edge: {(rec.edge * 100).toFixed(1)}%</span>}
        </div>
        <div className="text-xs text-white truncate">{rec.description || rec.market_id?.substring(0, 20)}</div>
        <div className="text-[10px] text-muted mt-0.5">{rec.reason?.substring(0, 80)}</div>
        {rec._execution?.error && (
          <div className="text-[10px] text-red-400 mt-1 truncate" title={rec._execution.error}>
            {String(rec._execution.error).substring(0, 100)}
          </div>
        )}
      </div>
      <div className="flex gap-2 shrink-0 items-center">
        {isPending && (
        <>
        <button onClick={() => handleAction('accept')}
          className="px-3 py-1.5 rounded-lg bg-green-500/20 text-green-400 text-xs font-semibold hover:bg-green-500/30 transition border border-green-500/30 flex items-center gap-1">
          ✓ Aprovar trade
          <HintTooltip skill="polywhale" hint="PolyWhale detectou edge. Ao aprovar, o Executor tenta comprar/vender via CLOB imediatamente." />
        </button>
        <button onClick={() => handleAction('reject')}
          className="px-3 py-1.5 rounded-lg bg-red-500/20 text-red-400 text-xs font-semibold hover:bg-red-500/30 transition border border-red-500/30 flex items-center gap-1">
          ✗ Descartar
          <HintTooltip hint="Ignora esta recomendação. O PolyWhale pode gerar nova sugestão no próximo ciclo." />
        </button>
        </>
        )}
      </div>
    </div>
  )
}
