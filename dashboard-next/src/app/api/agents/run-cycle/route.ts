import { NextResponse } from 'next/server'
import { spawnBackground } from '@/lib/spawnBackground'
import { generateCycleId, isCycleLockHeld, readCycleLockMeta } from '@/lib/loop'

export const dynamic = 'force-dynamic'

export async function POST() {
  try {
    if (isCycleLockHeld()) {
      const meta = readCycleLockMeta()
      return NextResponse.json(
        {
          ok: false,
          error: 'Ciclo em andamento',
          lock: meta,
        },
        { status: 409 },
      )
    }

    const cycleId = generateCycleId()
    const logFile = '/tmp/run-cycle-dashboard.log'

    spawnBackground(
      'bash',
      ['scripts/run-agents.sh', 'smart-cycle', '--with-lock', '--cycle-id', cycleId, '--source', 'dashboard'],
      logFile,
    )

    return NextResponse.json({
      ok: true,
      message: 'Ciclo inteligente iniciado em background',
      cycleId,
      logFile,
      phases: ['preflight', 'arbitrage', 'analysis', 'decision', 'execution', 'recovery', 'observability'],
    })
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Unknown error'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
