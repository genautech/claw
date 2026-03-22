'use client'

import { useEffect, useState } from 'react'
import {
  BarChart, Bar, PieChart, Pie, Cell, LineChart, Line,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend
} from 'recharts'

export default function TradesPage() {
  const [tab, setTab] = useState<'recs' | 'execs' | 'sims'>('execs')
  const [execData, setExecData] = useState<any>(null)
  const [recData, setRecData] = useState<any>(null)
  const [simData, setSimData] = useState<any>(null)

  useEffect(() => {
    fetch('/api/data?type=executions').then(r => r.json()).then(setExecData)
    fetch('/api/data?type=recommendations').then(r => r.json()).then(setRecData)
    fetch('/api/data?type=simulated').then(r => r.json()).then(setSimData)
  }, [])

  const tabs = [
    { key: 'execs', label: '⚡ Execuções', count: execData?.stats?.total || 0 },
    { key: 'recs', label: '🎯 Recomendações', count: recData?.stats?.total || 0 },
    { key: 'sims', label: '🧪 Simulações', count: simData?.total || 0 },
  ]

  // Chart data
  const decisionPieData = recData?.stats?.decisions
    ? Object.entries(recData.stats.decisions).map(([name, value]) => ({ name, value }))
    : []

  const hourlyData = execData?.stats?.hourly
    ? Object.entries(execData.stats.hourly).map(([hour, count]) => ({
        hour: `${hour}h`,
        trades: count,
      })).sort((a, b) => parseInt(a.hour) - parseInt(b.hour))
    : []

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#6366f1', '#ec4899']

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Trades & Charts</h1>
        <p className="text-sm text-muted mt-1">Planilha interativa de chamadas, recomendações e execuções</p>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Success Rate */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-white mb-4">📊 Taxa de Sucesso</h3>
          <div className="flex items-center justify-center">
            <div className="relative w-32 h-32">
              <svg className="w-32 h-32 -rotate-90" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="50" fill="none" stroke="#1e2d3d" strokeWidth="10" />
                <circle cx="60" cy="60" r="50" fill="none" stroke="#10b981" strokeWidth="10"
                  strokeDasharray={`${((execData?.stats?.success || 0) / Math.max(execData?.stats?.total || 1, 1)) * 314} 314`}
                  strokeLinecap="round" />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-2xl font-bold text-white">
                  {execData?.stats?.total ? Math.round((execData.stats.success / execData.stats.total) * 100) : 0}%
                </span>
                <span className="text-[10px] text-muted">{execData?.stats?.success || 0}/{execData?.stats?.total || 0}</span>
              </div>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2 text-center">
            <div>
              <div className="text-xs text-muted">Live</div>
              <div className="text-sm font-semibold text-white">{execData?.stats?.live || 0}</div>
            </div>
            <div>
              <div className="text-xs text-muted">Dry Run</div>
              <div className="text-sm font-semibold text-white">{execData?.stats?.dryRun || 0}</div>
            </div>
          </div>
        </div>

        {/* Decision Distribution */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-white mb-4">🎯 Distribuição de Decisões</h3>
          {decisionPieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={decisionPieData} cx="50%" cy="50%" innerRadius={45} outerRadius={70}
                  paddingAngle={3} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                  {decisionPieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1e2d3d', borderRadius: 8 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[200px] text-muted text-sm">Sem dados</div>
          )}
        </div>

        {/* Hourly Activity */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-white mb-4">🕐 Atividade por Hora</h3>
          {hourlyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={hourlyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e2d3d" />
                <XAxis dataKey="hour" stroke="#64748b" fontSize={10} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1e2d3d', borderRadius: 8 }} />
                <Bar dataKey="trades" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[200px] text-muted text-sm">Sem dados</div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {tabs.map(t => (
          <button key={t.key} onClick={() => setTab(t.key as any)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === t.key
                ? 'bg-accent/20 text-accent border border-accent/30'
                : 'bg-surface-2 text-muted border border-transparent hover:border-border'
            }`}>
            {t.label} <span className="ml-1 text-xs opacity-60">({t.count})</span>
          </button>
        ))}
      </div>

      {/* Data Tables */}
      <div className="glass-card p-5 overflow-x-auto">
        {tab === 'execs' && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Ação</th>
                <th>Market ID</th>
                <th>Side</th>
                <th>Outcome</th>
                <th>Size</th>
                <th>Price</th>
                <th>Status</th>
                <th>Detalhes</th>
              </tr>
            </thead>
            <tbody>
              {(execData?.data || []).slice().reverse().map((e: any, i: number) => (
                <tr key={i}>
                  <td className="font-mono text-xs text-muted whitespace-nowrap">
                    {new Date(e.timestamp).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td className="text-xs">{e.action?.replace(/_/g, ' ')}</td>
                  <td className="font-mono text-xs text-accent" title={e.details?.marketId}>
                    {(e.details?.gammaMarketId || e.details?.marketId || '').substring(0, 12)}...
                  </td>
                  <td>
                    <span className={`badge ${e.details?.side === 'buy' ? 'badge-success' : 'badge-danger'}`}>
                      {e.details?.side?.toUpperCase() || '—'}
                    </span>
                  </td>
                  <td className="text-xs">{e.details?.outcomeId || '—'}</td>
                  <td className="font-mono text-xs">${e.details?.sizeUsd?.toFixed(2) || '—'}</td>
                  <td className="font-mono text-xs">{e.details?.maxPrice?.toFixed(3) || '—'}</td>
                  <td>
                    <span className={`badge ${e.success ? 'badge-success' : 'badge-danger'}`}>
                      {e.success ? 'SUCCESS' : 'ERROR'}
                    </span>
                  </td>
                  <td className="text-xs text-muted max-w-[200px] truncate" title={e.error}>
                    {e.error || e.result?.orderId || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === 'recs' && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Mercado</th>
                <th>Decisão</th>
                <th>Confiança</th>
                <th>Target Price</th>
                <th>Edge</th>
                <th>Estratégia</th>
                <th>Motivo</th>
              </tr>
            </thead>
            <tbody>
              {(recData?.data || []).slice().reverse().map((r: any, i: number) => (
                <tr key={i}>
                  <td className="font-mono text-xs text-muted whitespace-nowrap">
                    {new Date(r.timestamp).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td className="text-xs max-w-[200px] truncate" title={r.description}>{r.description || r.market_id?.substring(0, 12)}</td>
                  <td>
                    <span className={`badge ${
                      r.decision?.includes('BUY') ? 'badge-success' : r.decision === 'PASS' ? 'badge-muted' : 'badge-warning'
                    }`}>
                      {r.decision}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${
                      r.confidence === 'HIGH' ? 'badge-success' : r.confidence === 'MEDIUM' ? 'badge-warning' : 'badge-muted'
                    }`}>
                      {r.confidence}
                    </span>
                  </td>
                  <td className="font-mono text-xs">{r.target_price?.toFixed(3) || '—'}</td>
                  <td className="font-mono text-xs">
                    {r.edge ? `${(r.edge * 100).toFixed(1)}%` : '—'}
                  </td>
                  <td className="text-xs">{r.strategy || '—'}</td>
                  <td className="text-xs text-muted max-w-[250px] truncate" title={r.reason}>{r.reason || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === 'sims' && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Mercado</th>
                <th>Decisão</th>
                <th>Confiança</th>
                <th>Target Price</th>
                <th>Edge</th>
                <th>Motivo</th>
              </tr>
            </thead>
            <tbody>
              {(simData?.data || []).slice().reverse().map((s: any, i: number) => (
                <tr key={i}>
                  <td className="font-mono text-xs text-muted whitespace-nowrap">
                    {new Date(s.timestamp).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td className="text-xs max-w-[200px] truncate">{s.description || s.market_id?.substring(0, 12)}</td>
                  <td>
                    <span className={`badge ${
                      s.decision?.includes('BUY') ? 'badge-success' : s.decision === 'PASS' ? 'badge-muted' : 'badge-warning'
                    }`}>
                      {s.decision}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${
                      s.confidence === 'HIGH' ? 'badge-success' : s.confidence === 'MEDIUM' ? 'badge-warning' : 'badge-muted'
                    }`}>
                      {s.confidence}
                    </span>
                  </td>
                  <td className="font-mono text-xs">{s.target_price?.toFixed(3) || '—'}</td>
                  <td className="font-mono text-xs">{s.edge ? `${(s.edge * 100).toFixed(1)}%` : '—'}</td>
                  <td className="text-xs text-muted max-w-[250px] truncate">{s.reason || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
