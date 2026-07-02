'use client'

import { useCallback, useEffect, useState } from 'react'
import { useDashboardData } from '@/hooks/useDashboardData'

export type ExecutionMode = 'MONITORING' | 'ARMED' | 'LIVE' | 'OFFLINE'

export interface RealityStatus {
  mode?: ExecutionMode
  executorOnline?: boolean
  executorDryRun?: boolean
  autoExecute?: boolean
  smartLoop?: { running: boolean; pid: number | null }
  agents?: Record<string, { status: string; mode?: string }>
  ninjaAgentRunning?: boolean
}

interface RealityPanelProps {
  variant?: 'full' | 'compact'
  showActivateReal?: boolean
  onAutoExecuteChange?: (enabled: boolean) => void
  autoExecute?: boolean
}

type SystemRow = {
  name: string
  status: 'LIVE' | 'SIMULATED' | 'OFFLINE' | 'ARMED'
  detail: string
  action?: string
  actionFn?: () => void
  busy?: boolean
}

const STATUS_COLORS: Record<string, string> = {
  LIVE: 'badge-success',
  SIMULATED: 'badge-warning',
  OFFLINE: 'badge-danger',
  ARMED: 'badge-info',
}

export function RealityPanel({
  variant = 'full',
  showActivateReal = true,
  onAutoExecuteChange,
  autoExecute: externalAutoExecute,
}: RealityPanelProps) {
  const [data, setData] = useState<RealityStatus | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [confirmLive, setConfirmLive] = useState(false)

  const { data: rt } = useDashboardData<Record<string, unknown>>('/api/realtime', {
    intervalMs: variant === 'compact' ? 10000 : 5000,
    staleTimeMs: 4000,
  })
  const { data: modeData } = useDashboardData<Record<string, unknown>>('/api/executor/mode', {
    intervalMs: variant === 'compact' ? 10000 : 5000,
    staleTimeMs: 4000,
  })
  const { data: agentsRes, refresh: refreshAgents } = useDashboardData<{ agents?: RealityStatus['agents'] }>(
    '/api/agents',
    { intervalMs: variant === 'compact' ? 10000 : 5000, staleTimeMs: 5000 },
  )

  useEffect(() => {
    setData({
      mode: modeData?.mode as ExecutionMode | undefined,
      executorOnline: Boolean(modeData?.executorOnline ?? (rt?.executor && (rt.executor as Record<string, unknown>).online)),
      executorDryRun: modeData?.executorDryRun as boolean | undefined,
      autoExecute: (modeData?.autoExecute as boolean | undefined) ?? externalAutoExecute,
      smartLoop: rt?.smartLoop as RealityStatus['smartLoop'],
      agents: agentsRes?.agents,
      ninjaAgentRunning: rt?.ninjaAgentRunning as boolean | undefined,
    })
  }, [rt, modeData, agentsRes, externalAutoExecute])

  const refresh = useCallback(async () => {
    await refreshAgents(true)
  }, [refreshAgents])

  const agentAction = async (agent: string, action: 'start' | 'stop') => {
    setBusy(`${agent}-${action}`)
    try {
      await fetch('/api/agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent, action }),
      })
      await refresh()
    } finally {
      setBusy(null)
    }
  }

  const loopAction = async (action: 'start' | 'stop') => {
    setBusy(`loop-${action}`)
    try {
      await fetch(`/api/loop/${action}`, { method: 'POST' })
      await refresh()
    } finally {
      setBusy(null)
    }
  }

  const activateReal = async () => {
    if (!confirmLive) {
      setConfirmLive(true)
      return
    }
    setBusy('activate-real')
    try {
      const res = await fetch('/api/executor/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'activate_real', confirmed: true }),
      })
      const body = await res.json()
      if (!res.ok) alert(body.error || 'Falha ao ativar modo real')
      else {
        onAutoExecuteChange?.(true)
        setConfirmLive(false)
      }
      await refresh()
    } finally {
      setBusy(null)
    }
  }

  const setDryRun = async () => {
    setBusy('dry-run')
    try {
      await fetch('/api/executor/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'dry' }),
      })
      onAutoExecuteChange?.(false)
      setConfirmLive(false)
      await refresh()
    } finally {
      setBusy(null)
    }
  }

  const mode = data?.mode ?? 'OFFLINE'
  const executorLive = data?.executorOnline && data?.executorDryRun === false
  const brimoActive = data?.agents?.Brimo?.status === 'active'
  const ninjaAgent = data?.ninjaAgentRunning

  const rows: SystemRow[] = [
    {
      name: 'Order Book CLOB',
      status: 'LIVE',
      detail: 'WebSocket direto Polymarket',
    },
    {
      name: 'Executor CLOB',
      status: !data?.executorOnline ? 'OFFLINE' : executorLive ? 'LIVE' : 'SIMULATED',
      detail: data?.executorOnline
        ? executorLive ? 'Ordens reais habilitadas' : 'DRY_RUN ativo no executor'
        : 'Porta 8789 offline',
      action: !data?.executorOnline ? 'Iniciar Executor' : undefined,
      actionFn: !data?.executorOnline ? () => agentAction('Executor', 'start') : undefined,
      busy: busy === 'Executor-start',
    },
    {
      name: 'Arbitrage Auto-Exec',
      status: mode === 'LIVE' ? 'LIVE' : mode === 'ARMED' ? 'ARMED' : 'SIMULATED',
      detail:
        mode === 'LIVE'
          ? 'Auto-exec + executor live'
          : mode === 'ARMED'
            ? 'Auto-exec ON mas executor em dry-run'
            : 'Apenas PnL simulado no browser',
    },
    {
      name: 'ArbitrageNinja Agent',
      status: ninjaAgent ? 'LIVE' : 'OFFLINE',
      detail: ninjaAgent ? 'Processo Python rodando' : 'Agent não iniciado (só UI browser)',
      action: ninjaAgent ? 'Parar Agent' : 'Iniciar Agent',
      actionFn: () => agentAction('ArbitrageNinja', ninjaAgent ? 'stop' : 'start'),
      busy: busy === 'ArbitrageNinja-start' || busy === 'ArbitrageNinja-stop',
    },
    {
      name: 'Smart Loop',
      status: data?.smartLoop?.running ? 'LIVE' : 'OFFLINE',
      detail: data?.smartLoop?.running
        ? `PID ${data.smartLoop.pid ?? '?'}`
        : 'Ciclo 24/7 parado',
      action: data?.smartLoop?.running ? 'Parar Loop' : 'Iniciar Loop',
      actionFn: () => loopAction(data?.smartLoop?.running ? 'stop' : 'start'),
      busy: busy === 'loop-start' || busy === 'loop-stop',
    },
    {
      name: 'Brimo',
      status: brimoActive ? 'LIVE' : 'OFFLINE',
      detail: brimoActive ? 'Monitor de posições ativo' : 'Daemon parado',
      action: brimoActive ? 'Parar Brimo' : 'Iniciar Brimo',
      actionFn: () => agentAction('Brimo', brimoActive ? 'stop' : 'start'),
      busy: busy === 'Brimo-start' || busy === 'Brimo-stop',
    },
  ]

  const displayRows = variant === 'compact' ? rows.slice(0, 4) : rows

  return (
    <div className="glass-card p-4 border border-border/60">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div>
          <h3 className="text-sm font-semibold text-white">Painel de Realidade</h3>
          <p className="text-[10px] text-muted mt-0.5">
            Modo atual:{' '}
            <span className={`badge text-[9px] ml-1 ${STATUS_COLORS[mode] || 'badge-muted'}`}>
              {mode}
            </span>
          </p>
        </div>
        {showActivateReal && (
          <div className="flex gap-2 flex-wrap">
            {confirmLive ? (
              <>
                <button
                  onClick={activateReal}
                  disabled={busy === 'activate-real'}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold bg-red-600 text-white hover:bg-red-500 disabled:opacity-50"
                >
                  {busy === 'activate-real' ? 'Ativando...' : 'Confirmar LIVE'}
                </button>
                <button
                  onClick={() => setConfirmLive(false)}
                  className="px-3 py-1.5 rounded-lg text-xs border border-border text-muted"
                >
                  Cancelar
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={activateReal}
                  disabled={mode === 'LIVE' || !!busy}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-green-500/20 text-green-400 border border-green-500/30 hover:bg-green-500/30 disabled:opacity-40"
                >
                  Ativar modo real
                </button>
                {mode !== 'MONITORING' && (
                  <button
                    onClick={setDryRun}
                    disabled={!!busy}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30"
                  >
                    Voltar simulação
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </div>

      <div className={`grid gap-2 ${variant === 'compact' ? 'grid-cols-1' : 'grid-cols-1 md:grid-cols-2'}`}>
        {displayRows.map((row) => (
          <div
            key={row.name}
            className="flex items-center justify-between gap-2 p-2 rounded-lg bg-surface-2/50 border border-border/30"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-white truncate">{row.name}</span>
                <span className={`badge text-[8px] shrink-0 ${STATUS_COLORS[row.status]}`}>
                  {row.status}
                </span>
              </div>
              <p className="text-[10px] text-muted truncate">{row.detail}</p>
            </div>
            {row.action && row.actionFn && (
              <button
                onClick={row.actionFn}
                disabled={row.busy}
                className="shrink-0 px-2 py-1 rounded text-[10px] font-semibold bg-accent/20 text-accent border border-accent/30 hover:bg-accent/30 disabled:opacity-50"
              >
                {row.busy ? '...' : row.action}
              </button>
            )}
          </div>
        ))}
      </div>

      {variant === 'full' && (
        <p className="text-[10px] text-muted mt-3 border-t border-border/30 pt-2">
          KPI &quot;Simulated PnL&quot; é sempre estimativa local. Ordens reais exigem Executor LIVE + Auto-Exec.
          Histórico com <code className="text-accent">live_order_id</code> = execução confirmada.
        </p>
      )}
    </div>
  )
}
