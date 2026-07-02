import { NextResponse } from 'next/server'
import { existsSync, unlinkSync } from 'fs'
import { getSmartLoopPid, SMART_LOOP_PID_FILE } from '@/lib/loop'

export const dynamic = 'force-dynamic'

export async function POST() {
  try {
    const pid = getSmartLoopPid()
    if (!pid) {
      return NextResponse.json({
        ok: true,
        message: 'Smart Loop não estava rodando',
        wasRunning: false,
      })
    }

    try {
      process.kill(pid, 'SIGTERM')
    } catch {
      return NextResponse.json({
        ok: false,
        error: `Não foi possível parar o processo ${pid}`,
      }, { status: 500 })
    }

    if (existsSync(SMART_LOOP_PID_FILE)) {
      try {
        unlinkSync(SMART_LOOP_PID_FILE)
      } catch {
        // ignore
      }
    }

    return NextResponse.json({
      ok: true,
      message: 'Smart Loop parado',
      stoppedPid: pid,
    })
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Unknown error'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
