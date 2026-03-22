'use client'

import { useEffect, useState } from 'react'
import {
  BarChart, Bar, PieChart, Pie, Cell, RadarChart, Radar, PolarGrid, PolarAngleAxis,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts'

export default function AnalysisPage() {
  const [execData, setExecData] = useState<any>(null)
  const [recData, setRecData] = useState<any>(null)
  const [simData, setSimData] = useState<any>(null)
  const [approving, setApproving] = useState<Record<string, boolean>>({})
  const [approvedFixes, setApprovedFixes] = useState<Record<string, boolean>>({})

  const handleApproveFix = async (errorName: string, recommendation: string) => {
    setApproving(prev => ({ ...prev, [errorName]: true }))
    try {
      await fetch('/api/corrections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ errorName, action: recommendation })
      })
      setApprovedFixes(prev => ({ ...prev, [errorName]: true }))
    } catch (e) {
      console.error('Failed to approve correction', e)
    } finally {
      setApproving(prev => ({ ...prev, [errorName]: false }))
    }
  }

  useEffect(() => {
    fetch('/api/data?type=executions').then(r => r.json()).then(setExecData)
    fetch('/api/data?type=recommendations').then(r => r.json()).then(setRecData)
    fetch('/api/data?type=simulated').then(r => r.json()).then(setSimData)
  }, [])

  // Analyze strategies from simulated data
  const strategyPerf = (() => {
    if (!simData?.data) return []
    const strats: Record<string, { total: number; buy: number; pass: number; avgConf: number }> = {}
    const confMap: Record<string, number> = { LOW: 1, MEDIUM: 2, HIGH: 3 }

    simData.data.forEach((s: any) => {
      const st = s.strategy || 'unknown'
      if (!strats[st]) strats[st] = { total: 0, buy: 0, pass: 0, avgConf: 0 }
      strats[st].total++
      if (s.decision?.includes('BUY')) strats[st].buy++
      else strats[st].pass++
      strats[st].avgConf += confMap[s.confidence] || 1
    })

    return Object.entries(strats)
      .map(([name, s]) => ({
        name: name.substring(0, 14),
        total: s.total,
        buyRate: Math.round((s.buy / s.total) * 100),
        avgConfidence: Math.round((s.avgConf / s.total) * 33),
      }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 8)
  })()

  // Confidence distribution
  const confDist = (() => {
    if (!simData?.data) return []
    const conf: Record<string, number> = {}
    simData.data.forEach((s: any) => {
      const c = s.confidence || 'UNKNOWN'
      conf[c] = (conf[c] || 0) + 1
    })
    return Object.entries(conf).map(([name, value]) => ({ name, value }))
  })()

  // Error analysis
  const errorAnalysis = (() => {
    if (!execData?.stats?.errorTypes) return []
    return Object.entries(execData.stats.errorTypes)
      .map(([name, count]) => ({ name, count, percentage: 0 }))
      .map((item, _, arr) => {
        const total = arr.reduce((s, i) => s + (i.count as number), 0)
        return { ...item, percentage: Math.round(((item.count as number) / total) * 100) }
      })
      .sort((a, b) => (b.count as number) - (a.count as number))
  })()

  // Market diversity (unique markets analyzed)
  const marketStats = (() => {
    if (!simData?.data) return { total: 0, unique: 0, avgEdge: 0 }
    const markets = new Set(simData.data.map((s: any) => s.market_id))
    const edges = simData.data.filter((s: any) => s.edge).map((s: any) => s.edge)
    return {
      total: simData.data.length,
      unique: markets.size,
      avgEdge: edges.length > 0 ? edges.reduce((a: number, b: number) => a + b, 0) / edges.length : 0,
    }
  })()

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#6366f1', '#ec4899', '#14b8a6', '#a855f7']

  return (
    <div className="space-y-6 max-w-[1400px]">
      <div>
        <h1 className="text-2xl font-bold text-white">Análise & Tendências</h1>
        <p className="text-sm text-muted mt-1">Análise profunda de estratégias, mercados e performance dos agentes</p>
      </div>

      {/* Overview KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass-card p-4 text-center">
          <div className="text-xs text-muted mb-1">Mercados Analisados</div>
          <div className="text-2xl font-bold text-white">{marketStats.unique}</div>
          <div className="text-xs text-muted">de {marketStats.total} recomendações</div>
        </div>
        <div className="glass-card p-4 text-center">
          <div className="text-xs text-muted mb-1">Edge Médio</div>
          <div className="text-2xl font-bold text-accent">{(marketStats.avgEdge * 100).toFixed(1)}%</div>
          <div className="text-xs text-muted">vantagem detectada</div>
        </div>
        <div className="glass-card p-4 text-center">
          <div className="text-xs text-muted mb-1">Estratégias Ativas</div>
          <div className="text-2xl font-bold text-white">{strategyPerf.length}</div>
          <div className="text-xs text-muted">em uso pelo sistema</div>
        </div>
        <div className="glass-card p-4 text-center">
          <div className="text-xs text-muted mb-1">Taxa de Erro</div>
          <div className="text-2xl font-bold text-danger">
            {execData?.stats?.total ? Math.round((execData.stats.errors / execData.stats.total) * 100) : 0}%
          </div>
          <div className="text-xs text-muted">{execData?.stats?.errors || 0} erros</div>
        </div>
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Strategy Performance */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-white mb-4">🧠 Performance das Estratégias</h3>
          {strategyPerf.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={strategyPerf} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#1e2d3d" />
                <XAxis type="number" stroke="#64748b" fontSize={10} />
                <YAxis type="category" dataKey="name" stroke="#64748b" fontSize={10} width={100} />
                <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1e2d3d', borderRadius: 8 }} />
                <Bar dataKey="total" fill="#3b82f6" radius={[0, 4, 4, 0]} name="Total Trades" />
                <Bar dataKey="buyRate" fill="#10b981" radius={[0, 4, 4, 0]} name="Buy Rate %" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[280px] text-muted text-sm">Carregando...</div>
          )}
        </div>

        {/* Confidence Distribution */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-white mb-4">📊 Distribuição de Confiança</h3>
          {confDist.length > 0 ? (
            <div>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={confDist} cx="50%" cy="50%" innerRadius={50} outerRadius={80}
                    paddingAngle={3} dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                    {confDist.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1e2d3d', borderRadius: 8 }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="mt-2 space-y-1">
                {confDist.map((c, i) => (
                  <div key={c.name} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-sm" style={{ background: COLORS[i % COLORS.length] }} />
                      <span className="text-muted">{c.name}</span>
                    </div>
                    <span className="font-mono text-white">{c.value}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-[280px] text-muted text-sm">Carregando...</div>
          )}
        </div>
      </div>

      {/* Error Analysis */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-white mb-4">🔴 Análise de Erros — Prioridades de Correção</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-3">
            {errorAnalysis.map((err, i) => (
              <div key={err.name}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-muted">{err.name}</span>
                  <span className="text-xs font-mono text-white">{err.count as number}x ({err.percentage}%)</span>
                </div>
                <div className="progress-bar">
                  <div className="progress-bar-fill" style={{
                    width: `${err.percentage}%`,
                    background: i === 0 ? '#ef4444' : i === 1 ? '#f59e0b' : '#3b82f6'
                  }} />
                </div>
              </div>
            ))}
            {errorAnalysis.length === 0 && <p className="text-sm text-muted">Sem erros registrados</p>}
          </div>
          <div className="space-y-3">
            <h4 className="text-xs font-semibold text-white uppercase tracking-wide">🔧 Ações Recomendadas</h4>
            {errorAnalysis.slice(0, 4).map((err) => {
              let recommendation = ''
              if (err.name === 'Invalid Market ID') recommendation = 'Implementar cache de market IDs válidos e validação upfront'
              else if (err.name === 'Balance/Allowance') recommendation = 'Verificar saldo USDC sugerindo proxy check e aprove onchain'
              else if (err.name === 'Invalid Signature') recommendation = 'Regenerar chaves API do Polymarket e verificar assinatura'
              else if (err.name === 'Missing Config') recommendation = 'Configurar POLYMARKET_PK e POLYMARKET_ADDRESS no ~/.openclaw/openclaw.json'
              else if (err.name === 'Auth Error') recommendation = 'Renovar sessões e API keys no ~/.openclaw'
              else if (err.name === 'Division by Zero') recommendation = 'Adicionar guards para valores zero em cálculos de edge/price'
              else recommendation = 'Investigar e corrigir log stack trace na base do projeto'

              const isPending = approving[err.name]
              const isApproved = approvedFixes[err.name]

              return (
                <div key={err.name} className="glass-card p-3 border-l-2 border-danger space-y-2">
                  <div className="text-xs font-medium text-white">{err.name}</div>
                  <div className="text-[11px] text-muted">{recommendation}</div>
                  <div className="pt-2 flex justify-end">
                    <button 
                      className={`text-[10px] px-3 py-1.5 rounded-md font-semibold transition-all ${isApproved ? 'bg-success/20 text-success cursor-default' : 'bg-accent/20 text-accent hover:bg-accent hover:text-white'}`}
                      onClick={() => !isApproved && handleApproveFix(err.name, recommendation)}
                      disabled={isPending || isApproved}
                    >
                      {isPending ? '⏳ Enviando...' : isApproved ? '✅ Aprovada / Em progresso' : '🚀 Aprovar Correção'}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
