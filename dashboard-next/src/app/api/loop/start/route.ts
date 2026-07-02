import { NextResponse } from 'next/server'
import { spawnBackground } from '@/lib/spawnBackground'
import { isSmartLoopRunning } from '@/lib/loop'

export const dynamic = 'force-dynamic'

export async function POST() {
  try {
    if (isSmartLoopRunning()) {
      return NextResponse.json({
        ok: true,
        message: 'Smart Loop já está rodando',
        alreadyRunning: true,
      })
    }

    const logFile = '/tmp/smart-loop.log'
    spawnBackground('bash', ['scripts/start-autoloop.sh'], logFile)

    return NextResponse.json({
      ok: true,
      message: 'Smart Loop iniciado em background',
      logFile,
      stateFile: 'data/loop-state.json',
    })
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Unknown error'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
