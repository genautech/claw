'use client'

import { useEffect, useState } from 'react'
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, LineChart, Line,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend
} from 'recharts'

interface CostData {
  tradingFees: number
  totalApiCost: number
  totalTokens: number
  costPerTrade: number
  tokenBreakdown: {
    model: string
    calls: number
    tokensUsed: number
    costInput: number
    costOutput: number
    totalCost: number
  }[]
  dailyCosts: {
    date: string
    tradingFees: number
    apiCost: number
    gasFees: number
  }[]
}

const MODEL_PRICES = {
  'gemini-2.5-flash': { input: '$0.15/1M', output: '$0.60/1M', tier: 'budget' },
  'claude-sonnet-4-5': { input: '$3.00/1M', output: '$15.00/1M', tier: 'premium' },
  'gpt-4o': { input: '$2.50/1M', output: '$10.00/1M', tier: 'premium' },
  'grok': { input: '$5.00/1M', output: '$15.00/1M', tier: 'premium' },
  'deepseek': { input: '$0.14/1M', output: '$0.28/1M', tier: 'budget' },
  'r1': { input: '$0.80/1M', output: '$1.60/1M', tier: 'mid' },
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#6366f1', '#ec4899']
const TIER_COLORS: Record<string, string> = {
  budget: '#10b981',
  mid: '#f59e0b',
  premium: '#ef4444',
}

export default function CostsPage() {
  const [costs, setCosts] = useState<CostData | null>(null)

  useEffect(() => {
    fetch('/api/data?type=costs').then(r => r.json()).then(setCosts)
  }, [])

  const totalCost = costs ? costs.tradingFees + costs.totalApiCost : 0
  const dailyTotal = costs?.dailyCosts?.map(d => ({
    ...d,
    total: d.tradingFees + d.apiCost + d.gasFees,
  })) || []

  // Cost breakdown for pie chart
  const costBreakdown = costs ? [
    { name: 'Trading Fees', value: costs.tradingFees },
    { name: 'API Tokens', value: costs.totalApiCost },
    { name: 'Gas Fees', value: costs.dailyCosts?.reduce((s, d) => s + d.gasFees, 0) || 0 },
  ] : []

  // Optimization recommendations
  const optimizations = [
    {
      title: '🔄 Substituir Claude Sonnet por Gemini Flash',
      desc: 'Para tarefas não-críticas (scan de mercados), usar gemini-2.5-flash ao invés de claude-sonnet-4-5',
      saving: costs?.tokenBreakdown?.find(t => t.model === 'claude-sonnet-4-5')?.totalCost
        ? `~$${(costs.tokenBreakdown.find(t => t.model === 'claude-sonnet-4-5')!.totalCost * 0.8).toFixed(4)}`
        : '~80%',
      impact: 'high',
    },
    {
      title: '⏱️ Reduzir Frequência de Scan',
      desc: 'Quando edge < 5%, aumentar intervalo de scan de 15min para 30min',
      saving: '~40% tokens de scan',
      impact: 'medium',
    },
    {
      title: '📦 Batch Recommendations',
      desc: 'Agrupar mercados similares em uma única chamada de API ao invés de chamadas individuais',
      saving: '~30% tokens',
      impact: 'medium',
    },
    {
      title: '💾 Cache de Respostas',
      desc: 'Cachear market data por 5min para evitar chamadas repetidas à API do Polymarket',
      saving: '~25% API calls',
      impact: 'low',
    },
    {
      title: '🧹 Filtrar Markets Upfront',
      desc: 'Pré-filtrar mercados por volume e liquidez antes de enviar para análise AI',
      saving: '~50% tokens de análise',
      impact: 'high',
    },
  ]

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">💰 Custos & Fees</h1>
          <p className="text-sm text-muted mt-1">
            Monitoramento de gastos com trading fees, API tokens, e otimização de custos
          </p>
        </div>
        <div className="badge badge-warning">⚠️ Custo é Inimigo do Lucro</div>
      </div>

      {/* Cost KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <CostKpi label="Custo Total" value={`$${totalCost.toFixed(4)}`} icon="💸" trend="—" />
        <CostKpi label="Trading Fees" value={`$${(costs?.tradingFees || 0).toFixed(4)}`} icon="📊" trend="—" />
        <CostKpi label="API Tokens" value={`$${(costs?.totalApiCost || 0).toFixed(4)}`} icon="🤖" trend="—" />
        <CostKpi label="Tokens Usados" value={formatTokens(costs?.totalTokens || 0)} icon="📝" trend="—" />
        <CostKpi label="Custo/Trade" value={`$${(costs?.costPerTrade || 0).toFixed(4)}`} icon="⚡" trend="—" />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Daily Cost Timeline */}
        <div className="glass-card p-5 lg:col-span-2">
          <h3 className="text-sm font-semibold text-white mb-4">📈 Custos ao Longo do Tempo</h3>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={dailyTotal}>
              <defs>
                <linearGradient id="colorTrading" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorApi" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorGas" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2d3d" />
              <XAxis dataKey="date" stroke="#64748b" fontSize={10} tickLine={false}
                tickFormatter={v => v.split('-').slice(1).join('/')} />
              <YAxis stroke="#64748b" fontSize={10} tickLine={false} tickFormatter={v => `$${v.toFixed(3)}`} />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #1e2d3d', borderRadius: 8 }}
                formatter={(value: number) => [`$${value.toFixed(4)}`, '']}
              />
              <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
              <Area type="monotone" dataKey="tradingFees" stroke="#3b82f6" fill="url(#colorTrading)" strokeWidth={2} name="Trading Fees" />
              <Area type="monotone" dataKey="apiCost" stroke="#f59e0b" fill="url(#colorApi)" strokeWidth={2} name="API Tokens" />
              <Area type="monotone" dataKey="gasFees" stroke="#ef4444" fill="url(#colorGas)" strokeWidth={2} name="Gas Fees" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Cost Breakdown Pie */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-white mb-4">🍕 Breakdown de Custos</h3>
          {costBreakdown.length > 0 ? (
            <div>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={costBreakdown} cx="50%" cy="50%" innerRadius={40} outerRadius={70}
                    paddingAngle={3} dataKey="value"
                    label={({ name, percent }) => `${(percent * 100).toFixed(0)}%`}>
                    {costBreakdown.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: '#111827', border: '1px solid #1e2d3d', borderRadius: 8 }}
                    formatter={(value: number) => [`$${value.toFixed(4)}`, '']}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="mt-2 space-y-2">
                {costBreakdown.map((c, i) => (
                  <div key={c.name} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-sm" style={{ background: COLORS[i] }} />
                      <span className="text-muted">{c.name}</span>
                    </div>
                    <span className="font-mono text-white">${c.value.toFixed(4)}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-[260px] text-muted text-sm">Carregando...</div>
          )}
        </div>
      </div>

      {/* Token Usage by Model */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-white mb-4">🤖 Consumo de Tokens por Modelo de AI</h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Chart */}
          <div>
            {costs?.tokenBreakdown && costs.tokenBreakdown.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={costs.tokenBreakdown} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e2d3d" />
                  <XAxis type="number" stroke="#64748b" fontSize={10} tickFormatter={(v) => `$${v.toFixed(3)}`} />
                  <YAxis type="category" dataKey="model" stroke="#64748b" fontSize={10} width={120} />
                  <Tooltip
                    contentStyle={{ background: '#111827', border: '1px solid #1e2d3d', borderRadius: 8 }}
                    formatter={(value: number) => [`$${value.toFixed(4)}`, '']}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="costInput" fill="#3b82f6" radius={[0, 2, 2, 0]} name="Input Cost" stackId="a" />
                  <Bar dataKey="costOutput" fill="#6366f1" radius={[0, 4, 4, 0]} name="Output Cost" stackId="a" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-[280px] text-muted text-sm">Carregando...</div>
            )}
          </div>

          {/* Token Table */}
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Modelo</th>
                  <th>Tier</th>
                  <th>Preço Input</th>
                  <th>Preço Output</th>
                  <th>Calls Est.</th>
                  <th>Tokens</th>
                  <th>Custo Total</th>
                </tr>
              </thead>
              <tbody>
                {(costs?.tokenBreakdown || []).sort((a, b) => b.totalCost - a.totalCost).map((t) => {
                  const info = MODEL_PRICES[t.model as keyof typeof MODEL_PRICES]
                  return (
                    <tr key={t.model}>
                      <td className="font-mono text-xs text-accent">{t.model}</td>
                      <td>
                        <span className="badge" style={{
                          background: `${TIER_COLORS[info?.tier || 'mid']}20`,
                          color: TIER_COLORS[info?.tier || 'mid'],
                          border: `1px solid ${TIER_COLORS[info?.tier || 'mid']}40`,
                        }}>
                          {info?.tier || 'unknown'}
                        </span>
                      </td>
                      <td className="font-mono text-xs">{info?.input || '—'}</td>
                      <td className="font-mono text-xs">{info?.output || '—'}</td>
                      <td className="font-mono text-xs">{t.calls}</td>
                      <td className="font-mono text-xs">{formatTokens(t.tokensUsed)}</td>
                      <td className="font-mono text-xs font-semibold text-white">${t.totalCost.toFixed(4)}</td>
                    </tr>
                  )
                })}
              </tbody>
              {costs && (
                <tfoot>
                  <tr className="border-t border-border">
                    <td colSpan={5} className="text-xs font-semibold text-white py-2">TOTAL</td>
                    <td className="font-mono text-xs font-semibold text-white">{formatTokens(costs.totalTokens)}</td>
                    <td className="font-mono text-xs font-semibold text-accent">${costs.totalApiCost.toFixed(4)}</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </div>
      </div>

      {/* Cost Reduction Targets */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-white mb-4">🎯 Metas de Redução de Custos</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <ReductionTarget
            label="Custo API / Trade"
            current={costs?.costPerTrade || 0}
            target={(costs?.costPerTrade || 0) * 0.5}
            unit="$"
            color="#3b82f6"
          />
          <ReductionTarget
            label="Tokens por Recomendação"
            current={1200}
            target={600}
            unit=" tokens"
            color="#10b981"
          />
          <ReductionTarget
            label="Custo Mensal Total"
            current={totalCost * 30}
            target={totalCost * 30 * 0.4}
            unit="$"
            color="#f59e0b"
          />
        </div>
      </div>

      {/* Optimization Recommendations */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-white mb-4">💡 Recomendações de Otimização</h3>
        <div className="space-y-3">
          {optimizations.map((opt, i) => (
            <div key={i} className={`glass-card p-4 border-l-2 ${
              opt.impact === 'high' ? 'border-success' : opt.impact === 'medium' ? 'border-warning' : 'border-accent'
            }`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-white">{opt.title}</span>
                <div className="flex items-center gap-2">
                  <span className={`badge ${
                    opt.impact === 'high' ? 'badge-success' : opt.impact === 'medium' ? 'badge-warning' : 'badge-info'
                  }`}>
                    {opt.impact}
                  </span>
                  <span className="text-xs font-mono text-success">💚 {opt.saving}</span>
                </div>
              </div>
              <p className="text-xs text-muted">{opt.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function CostKpi({ label, value, icon, trend }: {
  label: string; value: string; icon: string; trend: string
}) {
  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-muted font-medium">{label}</span>
        <span className="text-base">{icon}</span>
      </div>
      <div className="text-xl font-bold text-white font-mono">{value}</div>
      <div className="text-[10px] text-muted mt-1">{trend}</div>
    </div>
  )
}

function ReductionTarget({ label, current, target, unit, color }: {
  label: string; current: number; target: number; unit: string; color: string
}) {
  const progress = target > 0 ? Math.min(((current - target) / current) * 100, 100) : 0
  const remaining = Math.max(0, ((current - target) / current) * 100)

  return (
    <div className="glass-card p-4">
      <div className="text-xs text-muted mb-2">{label}</div>
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-lg font-bold text-white font-mono">
          {unit === '$' ? `$${current.toFixed(4)}` : `${current.toFixed(0)}${unit}`}
        </span>
        <span className="text-xs text-success font-mono">
          → {unit === '$' ? `$${target.toFixed(4)}` : `${target.toFixed(0)}${unit}`}
        </span>
      </div>
      <div className="progress-bar">
        <div className="h-full rounded-full" style={{
          width: `${remaining}%`,
          background: `linear-gradient(90deg, ${color}, ${color}88)`,
        }} />
      </div>
      <div className="text-[10px] text-muted mt-1 text-right">
        Meta: reduzir {remaining.toFixed(0)}%
      </div>
    </div>
  )
}

function formatTokens(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return n.toString()
}
