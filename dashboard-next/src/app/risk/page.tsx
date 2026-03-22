'use client'

import { useEffect, useState } from 'react'
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid
} from 'recharts'

export default function RiskPage() {
  const [data, setData] = useState<any>(null)
  const [config, setConfig] = useState<any>(null)
  const [events, setEvents] = useState<any[]>([])

  const fetchAll = () => {
    fetch('/api/data?type=all').then(r => r.json()).then(setData).catch(() => {})
    fetch('/api/config').then(r => r.json()).then(setConfig).catch(() => {})
    fetch('/api/data?type=risk-events').then(r => r.json()).then(d => setEvents(d.events || [])).catch(() => {})
  }

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 15000)
    return () => clearInterval(interval)
  }, [])

  const balance = data?.balance?.usdc ?? config?.capitalInitial ?? 9
  const reserveFloor = config?.reserveFloor ?? 3
  const tp = config?.takeProfit ?? 20
  const sl = config?.stopLoss ?? 15
  const ts = config?.trailingStop ?? 10
  const maxDaily = config?.maxDailyExposure ?? 20
  const maxTrade = config?.maxTrade ?? 5

  // Simulated exposure (from execution data)
  const execStats = data?.executions?.stats
  const liveTradeCount = execStats?.live || 0
  const totalExposure = liveTradeCount * (maxTrade * 0.5) // estimated avg
  const exposurePct = balance > 0 ? Math.min((totalExposure / balance) * 100, 100) : 0
  const reserveBuffer = Math.max(balance - reserveFloor, 0)
  const reservePct = balance > 0 ? Math.min((reserveFloor / balance) * 100, 100) : 0

  // Exposure gauge data
  const gaugeData = [
    { name: 'Exposed', value: Math.min(exposurePct, 100), color: exposurePct > 70 ? '#ef4444' : '#3b82f6' },
    { name: 'Available', value: Math.max(100 - exposurePct, 0), color: '#1e2d3d' },
  ]

  // Event type distribution
  const eventTypes: Record<string, number> = {}
  events.forEach(e => {
    const t = e.event_type?.split('_')[0] || 'other'
    eventTypes[t] = (eventTypes[t] || 0) + 1
  })
  const eventChart = Object.entries(eventTypes).map(([type, count]) => ({
    type: type.charAt(0).toUpperCase() + type.slice(1),
    count,
  }))

  // Config update
  const handleConfigUpdate = async (key: string, value: number) => {
    const updated = { ...config, [key]: value }
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [key]: value }),
    })
    setConfig(updated)
  }

  return (
    <div className="space-y-5 max-w-[1400px]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">🛡️ Risk Management</h1>
          <p className="text-sm text-muted mt-1">Brimo Agent — Proteção de saldo e controle de risco</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="badge badge-success">🐻 Brimo Active</span>
          <span className="text-xs font-mono text-muted">Refresh: 15s</span>
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <RiskKpi label="Balance" value={`$${balance.toFixed(2)}`} icon="💰"
          color={balance > reserveFloor ? 'green' : 'red'} />
        <RiskKpi label="Reserve Floor" value={`$${reserveFloor.toFixed(2)}`} icon="🛡️"
          color={balance > reserveFloor ? 'blue' : 'red'}
          sub={`Buffer: $${reserveBuffer.toFixed(2)}`} />
        <RiskKpi label="Take Profit" value={`${tp}%`} icon="🎯" color="green" sub="Auto-sell when hit" />
        <RiskKpi label="Stop Loss" value={`-${sl}%`} icon="🛑" color="red" sub="Cut losses" />
        <RiskKpi label="Trailing Stop" value={`${ts}%`} icon="📉" color="amber" sub="From peak" />
        <RiskKpi label="Max Daily" value={`$${maxDaily}`} icon="📊" color="purple" sub="Exposure limit" />
      </div>

      {/* Main Grid: Gauges + Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Exposure Gauge */}
        <div className="glass-card p-5 flex flex-col items-center">
          <h3 className="text-sm font-semibold text-white mb-3 self-start">📊 Exposição do Bankroll</h3>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={gaugeData} cx="50%" cy="50%" innerRadius={55} outerRadius={75}
                paddingAngle={2} dataKey="value" startAngle={180} endAngle={0}>
                {gaugeData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
            </PieChart>
          </ResponsiveContainer>
          <div className="text-center -mt-4">
            <div className="text-2xl font-bold text-white">{exposurePct.toFixed(1)}%</div>
            <div className="text-xs text-muted">Exposto (~${totalExposure.toFixed(2)})</div>
          </div>
        </div>

        {/* Reserve Floor Meter */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-white mb-4">🛡️ Reserve Floor</h3>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-xs text-muted mb-1">
                <span>$0</span>
                <span className="text-white font-semibold">${balance.toFixed(2)}</span>
                <span>Max</span>
              </div>
              <div className="w-full h-6 rounded-full bg-surface-3 overflow-hidden relative">
                {/* Reserve floor zone (red) */}
                <div className="absolute inset-y-0 left-0 bg-red-500/30 border-r-2 border-red-500"
                  style={{ width: `${reservePct}%` }} />
                {/* Balance zone (green) */}
                <div className="absolute inset-y-0 left-0 bg-green-500/30"
                  style={{ width: `${Math.min((balance / (balance + 10)) * 100, 100)}%` }} />
              </div>
              <div className="flex justify-between text-[10px] text-muted mt-1">
                <span>Floor: ${reserveFloor}</span>
                <span className={balance > reserveFloor ? 'text-green-400' : 'text-red-400'}>
                  {balance > reserveFloor ? `✅ Safe (+$${reserveBuffer.toFixed(2)})` : '🚨 BELOW FLOOR'}
                </span>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-bg border border-border">
              <div className="text-xs text-muted mb-2">Ajustar Reserve Floor</div>
              <div className="flex items-center gap-2">
                <input type="range" min="0" max="10" step="0.5" value={reserveFloor}
                  onChange={e => handleConfigUpdate('reserveFloor', parseFloat(e.target.value))}
                  className="flex-1 accent-accent" />
                <span className="text-sm font-mono text-white w-12 text-right">${reserveFloor}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Quick TP/SL Controls */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-white mb-4">⚡ Controles Rápidos</h3>
          <div className="space-y-3">
            <RangeControl label="Take Profit" value={tp} min={5} max={100} step={5} unit="%"
              color="green" onChange={v => handleConfigUpdate('takeProfit', v)} />
            <RangeControl label="Stop Loss" value={sl} min={5} max={50} step={5} unit="%"
              color="red" onChange={v => handleConfigUpdate('stopLoss', v)} />
            <RangeControl label="Trailing Stop" value={ts} min={3} max={30} step={1} unit="%"
              color="amber" onChange={v => handleConfigUpdate('trailingStop', v)} />
            <RangeControl label="Max Daily Exposure" value={maxDaily} min={5} max={100} step={5} unit="$"
              color="blue" onChange={v => handleConfigUpdate('maxDailyExposure', v)} />
          </div>
        </div>
      </div>

      {/* Event Feed + Event Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Risk Events Feed */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-white mb-3">
            📜 Brimo Events
            <span className="ml-2 badge badge-muted">{events.length}</span>
          </h3>
          <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
            {events.length === 0 && (
              <div className="text-center text-muted text-sm py-8">
                <div className="text-2xl mb-2">🐻</div>
                Brimo aguardando... Inicie com:<br />
                <code className="text-xs text-accent">python scripts/brimo.py --monitor</code>
              </div>
            )}
            {events.slice().reverse().map((event, i) => (
              <EventCard key={i} event={event} />
            ))}
          </div>
        </div>

        {/* Event Type Distribution */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-white mb-3">📊 Distribuição de Eventos</h3>
          {eventChart.length > 0 ? (
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={eventChart} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#1e2d3d" />
                <XAxis type="number" stroke="#64748b" fontSize={11} />
                <YAxis dataKey="type" type="category" stroke="#64748b" fontSize={11} width={80} />
                <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1e2d3d', borderRadius: 8 }} />
                <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-center text-muted text-sm py-16">
              Sem eventos ainda
            </div>
          )}
        </div>
      </div>

      {/* Brimo Agent Info */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-white mb-3">🐻 Sobre o Brimo</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-lg bg-bg border border-border">
            <div className="text-sm font-semibold text-white mb-2">🎯 Take Profit</div>
            <div className="text-xs text-muted">
              Quando uma posição atinge {tp}% de lucro, Brimo vende automaticamente para garantir o ganho.
              Sell via FOK (Fill or Kill) no CLOB.
            </div>
          </div>
          <div className="p-4 rounded-lg bg-bg border border-border">
            <div className="text-sm font-semibold text-white mb-2">🛑 Stop Loss</div>
            <div className="text-xs text-muted">
              Se uma posição cai {sl}% do preço de entrada, Brimo corta a perda imediatamente.
              Protege contra quedas bruscas.
            </div>
          </div>
          <div className="p-4 rounded-lg bg-bg border border-border">
            <div className="text-sm font-semibold text-white mb-2">📉 Trailing Stop</div>
            <div className="text-xs text-muted">
              Rastreia o preço máximo de cada posição. Se o preço cai {ts}% do pico, vende.
              Permite capturar tendências de alta sem devolver os ganhos.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function RiskKpi({ label, value, icon, color, sub }: {
  label: string; value: string; icon: string; color: string; sub?: string
}) {
  const gradients: Record<string, string> = {
    blue: 'from-blue-500/10 to-indigo-500/5',
    purple: 'from-purple-500/10 to-pink-500/5',
    green: 'from-emerald-500/10 to-teal-500/5',
    amber: 'from-amber-500/10 to-orange-500/5',
    red: 'from-red-500/10 to-rose-500/5',
  }
  return (
    <div className={`glass-card p-3 bg-gradient-to-br ${gradients[color] || gradients.blue}`}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] text-muted uppercase tracking-wide">{label}</span>
        <span className="text-sm">{icon}</span>
      </div>
      <div className="text-lg font-bold text-white font-mono">{value}</div>
      {sub && <div className="text-[10px] text-muted">{sub}</div>}
    </div>
  )
}

function RangeControl({ label, value, min, max, step, unit, color, onChange }: {
  label: string; value: number; min: number; max: number; step: number; unit: string;
  color: string; onChange: (v: number) => void
}) {
  const colors: Record<string, string> = {
    green: 'text-green-400', red: 'text-red-400', amber: 'text-amber-400', blue: 'text-blue-400',
  }
  return (
    <div className="p-2.5 rounded-lg bg-bg border border-border">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-muted">{label}</span>
        <span className={`text-sm font-mono font-bold ${colors[color] || 'text-white'}`}>
          {unit === '$' ? `$${value}` : `${value}${unit}`}
        </span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(parseFloat(e.target.value))}
        className="w-full accent-accent h-1.5" />
    </div>
  )
}

function EventCard({ event }: { event: any }) {
  const isSuccess = event.success !== false
  const time = new Date(event.timestamp).toLocaleTimeString('pt-BR', {
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  })
  const typeColors: Record<string, string> = {
    sell: isSuccess ? 'border-green-400 bg-green-500/5' : 'border-red-400 bg-red-500/5',
    reserve: 'border-amber-400 bg-amber-500/5',
    brimo: 'border-blue-400 bg-blue-500/5',
    cycle: 'border-red-400 bg-red-500/5',
    position: 'border-purple-400 bg-purple-500/5',
  }
  const eventPrefix = event.event_type?.split('_')[0] || 'other'
  const borderClass = typeColors[eventPrefix] || 'border-border bg-surface/50'

  return (
    <div className={`rounded-lg px-3 py-2 border-l-2 ${borderClass}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-muted">{time}</span>
          <span className={`badge text-[9px] ${isSuccess ? 'badge-success' : 'badge-danger'}`}>
            {isSuccess ? 'OK' : 'FAIL'}
          </span>
        </div>
        <span className="text-[10px] text-muted">{event.event_type?.replace(/_/g, ' ')}</span>
      </div>
      {event.details && (
        <div className="text-[11px] text-accent font-mono mt-1 truncate">
          {event.details.reason || event.details.market_id?.substring(0, 20) || JSON.stringify(event.details).substring(0, 60)}
        </div>
      )}
      {event.error && <div className="text-[10px] text-red-400 mt-0.5 truncate">{event.error.substring(0, 50)}</div>}
    </div>
  )
}
