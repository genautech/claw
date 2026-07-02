'use client'

import { useEffect, useState } from 'react'
import { HintTooltip } from '@/components/HintTooltip'

const STRATEGIES = [
  {
    id: '5.1',
    name: 'Dynamic Rotation',
    hint: 'Bot rotaciona entre mercados crypto Up/Down com base em desequilíbrio do book.',
  },
  {
    id: '5.2',
    name: 'Temporal Arbitrage',
    hint: 'Explora diferença de preço entre janelas temporais do mesmo evento.',
  },
  {
    id: '5.3',
    name: 'Inventory Market-Making',
    hint: 'Market-making com gestão Avellaneda-Stoikov — lucra no spread.',
  },
  {
    id: '5.4',
    name: 'Hedged Directional',
    hint: 'Posição direcional com hedge parcial para limitar downside.',
  },
  {
    id: '5.5',
    name: 'Late-Resolution Capture',
    hint: 'Entra perto do fechamento quando probabilidade está mal precificada.',
  },
]

export default function BotsPage() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState<string | null>(null)

  const fetchData = () => {
    setLoading(true)
    fetch('/api/bots')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setData)
      .catch(() => setData({ analyses: [], watchlist: { wallets: [] }, stats: { botCount: 0 } }))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchData()
  }, [])

  const runOp = async (action: string) => {
    setRunning(action)
    try {
      await fetch('/api/ops', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      })
      setTimeout(fetchData, 3000)
    } finally {
      setRunning(null)
    }
  }

  return (
    <div className="space-y-6 max-w-[1400px]">
      {loading && !data && (
        <p className="text-sm text-muted">Carregando análises de bots...</p>
      )}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            🤖 Análise de Bots
            <HintTooltip
              skill="polybot-analyzer"
              hint="Polybot Analyzer estuda wallets concorrentes via data-api Polymarket e classifica estratégias lucrativas."
            />
          </h1>
          <p className="text-sm text-muted mt-1">
            Watchlist: {data?.watchlist?.wallets?.length || 0} wallets • {data?.stats?.botCount || 0} bots detectados
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <OpButton
            label="Analisar bots"
            running={running === 'analyze-bots'}
            onClick={() => runOp('analyze-bots')}
            hint="Executa agent_polybot_analyzer.py --all na watchlist."
            skill="polybot-analyzer"
          />
          <OpButton
            label="Calibrar minEdge"
            running={running === 'calibrate-edge'}
            onClick={() => runOp('calibrate-edge')}
            hint="Aplica edge sugerido pelos bots lucrativos em dashboard-config.json."
            skill="polybot-analyzer"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
        {STRATEGIES.map((s) => (
          <div key={s.id} className="glass-card p-3">
            <div className="text-[10px] text-accent font-mono">{s.id}</div>
            <div className="text-xs font-semibold text-white mt-1 flex items-center gap-1">
              {s.name}
              <HintTooltip hint={s.hint} skill="polybot-analyzer" />
            </div>
          </div>
        ))}
      </div>

      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-white mb-3">Últimas análises por wallet</h3>
        {!data?.analyses?.length ? (
          <p className="text-sm text-muted py-6 text-center">
            Nenhuma análise ainda. Clique em &quot;Analisar bots&quot;.
          </p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Wallet</th>
                <th>Estratégia</th>
                <th>Bot?</th>
                <th>Bot Ratio</th>
                <th>minEdge sugerido</th>
                <th>Analisado em</th>
              </tr>
            </thead>
            <tbody>
              {data.analyses.map((a: any, i: number) => (
                <tr key={i}>
                  <td className="font-mono text-xs text-accent">{String(a.wallet).substring(0, 12)}...</td>
                  <td className="text-xs">{a.strategy}</td>
                  <td>
                    <span className={`badge ${a.is_bot ? 'badge-success' : 'badge-muted'}`}>
                      {a.is_bot ? 'SIM' : 'NÃO'}
                    </span>
                  </td>
                  <td className="font-mono text-xs">{((a.bot_ratio || 0) * 100).toFixed(1)}%</td>
                  <td className="font-mono text-xs">{a.params?.suggested_min_edge ?? '—'}%</td>
                  <td className="text-[10px] text-muted">
                    {a.analyzed_at ? new Date(String(a.analyzed_at)).toLocaleString('pt-BR') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {data?.watchlist?.notes && (
        <div className="glass-card p-4 text-xs text-muted">{data.watchlist.notes}</div>
      )}
    </div>
  )
}

function OpButton({
  label,
  hint,
  skill,
  running,
  onClick,
}: {
  label: string
  hint: string
  skill?: string
  running: boolean
  onClick: () => void
}) {
  return (
    <div className="inline-flex items-center gap-1.5">
      <button
        type="button"
        onClick={onClick}
        disabled={running}
        className="px-4 py-2 rounded-lg text-sm font-semibold bg-accent/20 text-accent border border-accent/30 hover:bg-accent/30 disabled:opacity-50"
      >
        {running ? '⏳' : '🚀'} {label}
      </button>
      <HintTooltip hint={hint} skill={skill} />
    </div>
  )
}
