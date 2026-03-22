'use client'

import { useEffect, useState, useRef } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts'

interface Config {
  goal: number; goalDays: number; capitalInitial: number
  minTrade: number; maxTrade: number; dryRun: boolean
  takeProfit?: number; stopLoss?: number; trailingStop?: number
  reserveFloor?: number; maxDailyExposure?: number
}

export default function DashboardPage() {
  const [data, setData] = useState<any>(null)
  const [config, setConfig] = useState<Config | null>(null)
  const [recs, setRecs] = useState<any>(null)
  const [agentStatus, setAgentStatus] = useState<Record<string, string>>({})
  const feedRef = useRef<HTMLDivElement>(null)

  const [processingSync, setProcessingSync] = useState(false)

  const toggleAgent = async (agentName: string, currentStatus: string) => {
    const action = currentStatus === 'active' ? 'stop' : 'start'
    setAgentStatus(prev => ({ ...prev, [agentName]: action === 'start' ? 'active' : 'offline' }))
    try {
      await fetch('/api/agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent: agentName, action })
      })
    } catch {
      fetchAll() // Revert on fail
    }
  }

  const fetchAll = async () => {
    setProcessingSync(true)
    try {
      const [resData, resConfig, resRecs, resAgents] = await Promise.all([
        fetch('/api/data?type=all').then(r => r.json()).catch(() => null),
        fetch('/api/config').then(r => r.json()).catch(() => null),
        fetch('/api/recommendations').then(r => r.json()).catch(() => null),
        fetch('/api/agents').then(r => r.json()).catch(() => null)
      ])
      if (resData) setData(resData)
      if (resConfig) setConfig(resConfig)
      if (resRecs) setRecs(resRecs)
      if (resAgents?.statuses) setAgentStatus(resAgents.statuses)
    } finally {
      setProcessingSync(false)
    }
  }

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 10000)
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
  
  // Total Equity includes Cash + Value of Active Positions
  const portfolioValue = positions?.portfolioValue || 0
  const totalEquity = balanceUsd + portfolioValue
  const pnl = totalEquity > 0 ? totalEquity - capitalInitial : (stats?.totalPnl || 0)
  
  const progress = Math.min((totalEquity / goal) * 100, 100)
  const winRate = stats?.total > 0 ? Math.round((stats.success / stats.total) * 100) : 0
  const executorOnline = !health?.offline

  // Recent executions for feed
  const feedItems = (data?.executions?.data || []).slice().reverse()

  return (
    <div className="space-y-5 max-w-[1400px]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">🦞 PolyClaw Dashboard</h1>
          <p className="text-sm text-muted mt-1">Polymarket Trading — Definitivo</p>
        </div>
        <div className="flex items-center gap-3">
          <button 
            onClick={fetchAll} 
            disabled={processingSync}
            className={`px-4 py-2 rounded-lg text-sm font-bold border transition-colors ${processingSync ? 'bg-blue-500/20 text-blue-400 border-blue-500/40 cursor-wait' : 'bg-blue-600 text-white border-blue-500 hover:bg-blue-500 shadow-lg shadow-blue-500/20'}`}
          >
            {processingSync ? '🔄 Sincronizando...' : '🔄 Sincronizar Polymarket'}
          </button>
          
          <span className={`badge ${executorOnline ? 'badge-success' : 'badge-danger'}`}>
            {executorOnline ? '● Executor Online' : '● Executor Offline'}
          </span>
          <span className={`badge ${health?.dry_run ? 'badge-warning' : 'badge-success'}`}>
            {health?.dry_run ? '🧪 DRY RUN' : '🔴 LIVE'}
          </span>
          <span className="text-xs text-muted font-mono">
            {new Date().toLocaleString('pt-BR')}
          </span>
        </div>
      </div>

      {/* KPI Cards Row 1 */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <KpiCard label="Cash USDC" value={`$${balanceUsd.toFixed(2)}`}
          sub={balance?.address ? `${balance.address.substring(0, 8)}...` : 'wallet'}
          icon="💰" color="blue" />
        <KpiCard label="PnL Total" value={`${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`}
          sub={`Ativos: $${portfolioValue.toFixed(2)}`}
          icon={pnl >= 0 ? '📈' : '📉'} color={pnl >= 0 ? 'green' : 'red'} />
        <KpiCard label="Meta" value={`$${goal.toLocaleString()}`}
          sub={`${progress.toFixed(1)}% • ${goalDays}d`}
          icon="🎯" color="purple" progress={progress} />
        <KpiCard label="Win Rate" value={`${winRate}%`}
          sub={`${stats?.success || 0}W / ${stats?.errors || 0}L`}
          icon="🏆" color={winRate >= 60 ? 'green' : winRate >= 40 ? 'amber' : 'red'} />
        <KpiCard label="Trades Total" value={stats?.total?.toString() || '0'}
          sub={`${stats?.live || 0} live • ${stats?.dryRun || 0} dry`}
          icon="⚡" color="blue" />
        <KpiCard label="Recs Pendentes" value={recs?.stats?.pending?.toString() || '0'}
          sub={`${recs?.stats?.executed || 0} exec • ${recs?.stats?.rejected || 0} rej`}
          icon="🎯" color="amber" />
      </div>

      {/* Main Content: Feed + Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Charts */}
        <div className="lg:col-span-2 space-y-4">
          {/* Growth Chart */}
          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-white mb-3">📈 Projeção $9 → ${goal.toLocaleString()}</h3>
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

          {/* Agent Status */}
          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-white mb-3">🤖 Agentes em Atividade</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <AgentDetail name="PolyClaw" role="Market Scanner" status="active"
                details={['Sub-rotina de coleta do PolyWhale', `${data?.simulated?.total || 0} mercados analisados`, 'Gamma API + análise de spread']}
                model="gemini-flash" lastActive="integrado" />
              <AgentDetail name="PolyWhale" agentId="PolyWhale" role="Strategy & Recommendations" status={agentStatus['PolyWhale'] || 'offline'}
                details={[`${recs?.stats?.total || 0} recomendações geradas`, 'Estratégias: MVP, weather, carry', 'Análise de edge e confiança']}
                onToggle={() => toggleAgent('PolyWhale', agentStatus['PolyWhale'] || 'offline')}
                model="gemini-flash" lastActive={agentStatus['PolyWhale'] === 'active' ? 'agora' : 'offline'} />
              <AgentDetail name="CorrectionAgent" agentId="CorrectionAgent" role="Auto-Fix Daemon" status={agentStatus['CorrectionAgent'] || 'offline'}
                details={['Execução on-demand de fixes', 'Refatoração da ~/openclaw', 'Reinicio dinâmico das APIs', 'Escutando /api/corrections']}
                onToggle={() => toggleAgent('CorrectionAgent', agentStatus['CorrectionAgent'] || 'offline')}
                model="direct terminal" lastActive={agentStatus['CorrectionAgent'] === 'active' ? 'watch' : 'offline'} />
              <AgentDetail name="Brimo" agentId="Brimo" role="Sell Specialist" status={agentStatus['Brimo'] || 'offline'}
                details={[
                  `TP: ${config?.takeProfit ?? 20}% | SL: ${config?.stopLoss ?? 15}%`,
                  `Reserve Floor: $${config?.reserveFloor ?? 3}`,
                  `Trailing Stop: ${config?.trailingStop ?? 10}% do pico`,
                ]}
                onToggle={() => toggleAgent('Brimo', agentStatus['Brimo'] || 'offline')}
                model="position-monitor" lastActive={agentStatus['Brimo'] === 'active' ? '60s cycle' : 'offline'} />
              <AgentDetail name="Executor" agentId="Executor" role="Trade Execution" status={agentStatus['Executor'] || 'offline'}
                details={[
                  `Modo: ${health?.dry_run ? 'DRY RUN' : 'LIVE'}`,
                  `Max trade: $${health?.max_trade_usd || config?.maxTrade || '?'}`,
                  `Falhas consec.: ${health?.consecutive_failures || 0}`,
                ]}
                onToggle={() => toggleAgent('Executor', agentStatus['Executor'] || 'offline')}
                model="polymarket-exec" lastActive={agentStatus['Executor'] === 'active' ? 'online' : 'offline'} />
            </div>
          </div>
        </div>

        {/* Right: Live Trade Feed */}
        <div className="glass-card p-4 flex flex-col" style={{ maxHeight: 540 }}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-white">📜 Live Trade Feed</h3>
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

      {/* Pending Recommendations */}
      {recs?.recommendations?.filter((r: any) => r._status === 'pending').length > 0 && (
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-white mb-3">
            🎯 Recomendações Pendentes
            <span className="ml-2 badge badge-warning">{recs.stats.pending}</span>
          </h3>
          <div className="space-y-2">
            {recs.recommendations.filter((r: any) => r._status === 'pending').slice(0, 5).map((rec: any) => (
              <RecCard key={rec._id} rec={rec} onAction={fetchAll} />
            ))}
          </div>
        </div>
      )}

      {/* Active Positions */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-white mb-3">
          📊 Posições Ativas
          {positions?.offline && <span className="ml-2 badge badge-danger">Offline</span>}
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
              ? 'Executor offline — inicie com: python scripts/polymarket-exec.py --serve'
              : 'Sem posições ativas no momento'}
          </div>
        )}
      </div>
    </div>
  )
}

function generateGrowthData(start: number, target: number, days: number) {
  return Array.from({ length: days }, (_, i) => ({
    day: i + 1,
    target: start + ((target - start) / days) * (i + 1),
    projected: start + (target - start) * (1 - Math.exp(-(i + 1) / (days * 0.4))) * (1 + Math.sin(i / 4) * 0.03),
  }))
}

function KpiCard({ label, value, sub, icon, color, progress }: {
  label: string; value: string; sub: string; icon: string; color: string; progress?: number
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
          <span className="text-[10px] text-muted font-medium uppercase tracking-wide">{label}</span>
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

function AgentDetail({ name, agentId, role, status, details, model, lastActive, onToggle }: {
  name: string; agentId?: string; role: string; status: string; details: string[]; model: string; lastActive: string; onToggle?: () => void
}) {
  const isActive = status === 'active'
  const colors: Record<string, string> = { active: 'badge-success', offline: 'badge-danger', warning: 'badge-warning' }
  return (
    <div className="glass-card p-4 border border-border/50">
      <div className="flex items-center justify-between mb-2">
        <div>
          <span className="font-semibold text-sm text-white">{name}</span>
          <span className="text-xs text-muted ml-2">{role}</span>
        </div>
        <div className="flex items-center gap-2">
          {onToggle && agentId && (
            <button
              onClick={onToggle}
              title={isActive ? 'Desligar Agente' : 'Ligar Agente'}
              className={`relative inline-flex h-4 w-8 items-center rounded-full transition-colors focus:outline-none ${isActive ? 'bg-success' : 'bg-surface-2 border border-border'}`}
            >
              <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${isActive ? 'translate-x-4' : 'translate-x-0.5'}`} />
            </button>
          )}
          <span className={`badge ${colors[status] || 'badge-muted'}`}>{status.toUpperCase()}</span>
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

  return (
    <div className="glass-card p-3 flex items-center justify-between gap-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
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
      </div>
      <div className="flex gap-2 shrink-0">
        <button onClick={() => handleAction('accept')}
          className="px-3 py-1.5 rounded-lg bg-green-500/20 text-green-400 text-xs font-semibold hover:bg-green-500/30 transition border border-green-500/30">
          ✓ Aceitar
        </button>
        <button onClick={() => handleAction('reject')}
          className="px-3 py-1.5 rounded-lg bg-red-500/20 text-red-400 text-xs font-semibold hover:bg-red-500/30 transition border border-red-500/30">
          ✗ Rejeitar
        </button>
      </div>
    </div>
  )
}
