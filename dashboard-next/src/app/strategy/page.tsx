'use client'

import { useEffect, useState } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts'

interface Config {
  goal: number; goalDays: number; capitalInitial: number
  minTrade: number; maxTrade: number; maxDaily: number
}

export default function StrategyPage() {
  const [config, setConfig] = useState<Config | null>(null)
  const [data, setData] = useState<any>(null)

  useEffect(() => {
    fetch('/api/config').then(r => r.json()).then(setConfig)
    fetch('/api/data?type=all').then(r => r.json()).then(setData)
  }, [])

  const goal = config?.goal || 10000
  const goalDays = config?.goalDays || 30
  const startCapital = config?.capitalInitial || 9
  const currentCapital = data ? ((data.balance?.usdc || 0) + (data.positions?.portfolioValue || 0)) : startCapital
  
  const growthMultiple = goal / startCapital
  const dailyTarget = (goal - startCapital) / goalDays

  // Generate milestones based on actual config
  const weeksTotal = Math.ceil(goalDays / 7)
  const milestones = Array.from({ length: Math.min(weeksTotal, 8) }, (_, i) => {
    const week = i + 1
    const frac = week / weeksTotal
    const target = Math.round(startCapital + (goal - startCapital) * (1 - Math.exp(-frac * 3)) / (1 - Math.exp(-3)))
    const phases = [
      { desc: 'Setup & calibração', tasks: ['Corrigir erros de market ID', 'Configurar API keys', 'Primeiro trade live'] },
      { desc: 'Trades conservadores', tasks: ['Edge > 10%', `Max $${config?.maxTrade || 5}/trade`, 'Confidence HIGH'] },
      { desc: 'Expandir estratégias', tasks: ['Mais mercados', 'Weather + Carry', 'Position sizing dinâmico'] },
      { desc: 'Otimizar win rate', tasks: ['Analisar resultados', 'Ajustar thresholds', 'Reduzir custos 30%'] },
      { desc: 'Aumentar posições', tasks: ['Aumentar max trade', 'Diversificação', 'Real-time monitoring'] },
      { desc: 'Compound gains', tasks: ['Reinvestir lucros', 'Otimizar timing', 'Auto rebalancing'] },
      { desc: 'Scale up', tasks: ['HFT spreads', 'Cross-market arb', 'Multi-strategy'] },
      { desc: '🎯 Meta!', tasks: [`$${goal.toLocaleString()}/mês`, 'Review & docs', 'Auto-pilot'] },
    ]
    const phase = phases[Math.min(i, phases.length - 1)]
    return { week, target, ...phase, status: i === 0 ? 'active' : 'pending' }
  })

  const growthCurve = milestones.map(m => ({
    week: `S${m.week}`,
    target: m.target,
    conservative: Math.round(m.target * 0.6),
    optimistic: Math.round(m.target * 1.4),
  }))

  const riskRules = [
    { rule: 'Position Size Máximo', value: `${((config?.maxTrade || 5) / startCapital * 100).toFixed(0)}% do bankroll`, is: `$${config?.maxTrade || 5}` },
    { rule: 'Stop Loss por Trade', value: '-20%', is: `-$${((config?.maxTrade || 5) * 0.2).toFixed(2)}` },
    { rule: 'Trades/Dia Max', value: `$${config?.maxDaily || 20} total`, is: `~${Math.floor((config?.maxDaily || 20) / (config?.maxTrade || 5))} trades` },
    { rule: 'Min Edge', value: '8%+', is: '8%' },
    { rule: 'Min Confidence', value: 'HIGH', is: 'HIGH' },
    { rule: 'Max Drawdown', value: '-30% total', is: `-$${(startCapital * 0.3).toFixed(2)}` },
  ]

  return (
    <div className="space-y-6 max-w-[1400px]">
      <div>
        <h1 className="text-2xl font-bold text-white">🎯 Estratégia ${startCapital} → ${goal.toLocaleString()}</h1>
        <p className="text-sm text-muted mt-1">Roadmap de crescimento em {goalDays} dias</p>
      </div>

      {/* Status */}
      <div className="glass-card p-5 bg-gradient-to-r from-blue-500/5 to-purple-500/5">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          <div>
            <div className="text-xs text-muted">Capital Atual</div>
            <div className="text-3xl font-bold text-white">${currentCapital.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-xs text-muted">Meta</div>
            <div className="text-3xl font-bold text-accent">${goal.toLocaleString()}</div>
          </div>
          <div>
            <div className="text-xs text-muted">Crescimento</div>
            <div className="text-3xl font-bold text-warning">{growthMultiple.toFixed(0)}x</div>
          </div>
          <div>
            <div className="text-xs text-muted">Daily Target</div>
            <div className="text-3xl font-bold text-success">${dailyTarget.toFixed(2)}</div>
          </div>
        </div>
        <div className="mt-4">
          <div className="flex justify-between text-xs text-muted mb-1">
            <span>${startCapital.toFixed(2)}</span>
            <span>${goal.toLocaleString()}</span>
          </div>
          <div className="progress-bar h-3">
            <div className="progress-bar-fill h-full" style={{ width: `${(currentCapital / goal * 100).toFixed(1)}%` }} />
          </div>
        </div>
      </div>

      {/* Growth Chart */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-white mb-4">📈 Projeção de Crescimento</h3>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={growthCurve}>
            <defs>
              <linearGradient id="colorT" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e2d3d" />
            <XAxis dataKey="week" stroke="#64748b" fontSize={11} tickLine={false} />
            <YAxis stroke="#64748b" fontSize={11} tickLine={false} tickFormatter={v => `$${v >= 1000 ? (v/1000).toFixed(0) + 'k' : v}`} />
            <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1e2d3d', borderRadius: 8 }}
              formatter={(v: number) => [`$${v.toLocaleString()}`, '']} />
            <Area type="monotone" dataKey="conservative" stroke="#64748b" strokeDasharray="5 5" fill="none" name="Conservador" />
            <Area type="monotone" dataKey="target" stroke="#3b82f6" fill="url(#colorT)" strokeWidth={2} name="Target" />
            <Area type="monotone" dataKey="optimistic" stroke="#10b981" fill="none" strokeWidth={1} name="Otimista" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Milestones */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-white mb-4">🗺️ Milestones Semanais</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {milestones.map(m => (
            <div key={m.week} className={`glass-card p-4 border-l-2 ${m.status === 'active' ? 'border-accent' : 'border-border'}`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-muted">Semana {m.week}</span>
                <span className={`badge ${m.status === 'active' ? 'badge-info' : 'badge-muted'}`}>
                  {m.status === 'active' ? 'ATIVO' : 'PENDENTE'}
                </span>
              </div>
              <div className="text-lg font-bold text-white">${m.target.toLocaleString()}</div>
              <div className="text-xs text-muted mb-2">{m.desc}</div>
              <ul className="space-y-1">
                {m.tasks.map((t, i) => (
                  <li key={i} className="text-[11px] text-muted flex items-start gap-1">
                    <span className="mt-0.5">•</span><span>{t}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {/* Risk Management */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-white mb-4">🛡️ Gestão de Risco</h3>
        <table className="data-table">
          <thead>
            <tr><th>Regra</th><th>Limite</th><th>Valor</th></tr>
          </thead>
          <tbody>
            {riskRules.map(r => (
              <tr key={r.rule}>
                <td className="text-sm font-medium text-white">{r.rule}</td>
                <td><span className="badge badge-warning">{r.value}</span></td>
                <td className="font-mono text-sm">{r.is}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
