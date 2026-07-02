import { NextRequest, NextResponse } from 'next/server'
import { spawnBackground } from '@/lib/spawnBackground'
import { getDashboardConfig, saveDashboardConfig, syncDryRunToOpenclaw } from '@/lib/configSync'

export const dynamic = 'force-dynamic'

const EXECUTOR_URL = process.env.EXECUTOR_URL || 'http://127.0.0.1:8789'

async function executorHealth(): Promise<{ online: boolean; dry_run?: boolean }> {
  try {
    const res = await fetch(`${EXECUTOR_URL}/health`, { signal: AbortSignal.timeout(3000) })
    if (!res.ok) return { online: false }
    const data = await res.json()
    return { online: true, dry_run: Boolean(data.dry_run) }
  } catch {
    return { online: false }
  }
}

export async function GET() {
  const config = getDashboardConfig()
  const health = await executorHealth()
  const autoExecute = Boolean(config.autoExecute)
  const executorLive = health.online && !health.dry_run

  let mode: 'MONITORING' | 'ARMED' | 'LIVE' | 'OFFLINE' = 'MONITORING'
  if (!health.online) mode = 'OFFLINE'
  else if (autoExecute && executorLive) mode = 'LIVE'
  else if (autoExecute) mode = 'ARMED'

  return NextResponse.json({
    mode,
    executorOnline: health.online,
    executorDryRun: health.dry_run ?? config.dryRun,
    dashboardDryRun: config.dryRun,
    autoExecute,
  })
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const mode = body.mode as 'live' | 'dry' | 'activate_real'

    if (mode === 'activate_real') {
      const confirmed = body.confirmed === true
      if (!confirmed) {
        return NextResponse.json(
          { error: 'Confirmação obrigatória para modo live (confirmed: true)' },
          { status: 400 },
        )
      }

      let health = await executorHealth()
      if (!health.online) {
        spawnBackground('bash', ['scripts/start-executor.sh'], '/tmp/executor-start.log')
        await new Promise((r) => setTimeout(r, 3000))
        health = await executorHealth()
      }

      saveDashboardConfig({ dryRun: false, autoExecute: true })
      const sync = syncDryRunToOpenclaw(false)

      return NextResponse.json({
        ok: true,
        mode: 'LIVE',
        executorOnline: health.online,
        sync,
        hint: 'Reinicie o executor se DRY_RUN não aplicar: bash scripts/start-executor.sh',
      })
    }

    const dryRun = mode === 'dry'
    saveDashboardConfig({ dryRun, autoExecute: dryRun ? false : getDashboardConfig().autoExecute })
    const sync = syncDryRunToOpenclaw(dryRun)

    return NextResponse.json({
      ok: true,
      dryRun,
      sync,
      hint: sync.synced ? 'Reinicie o executor para aplicar DRY_RUN' : undefined,
    })
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Unknown error'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
