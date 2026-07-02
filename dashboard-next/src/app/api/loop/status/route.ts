import { NextResponse } from 'next/server'
import {
  getLoopState,
  getLoopConfig,
  isCycleLockHeld,
  isSmartLoopRunning,
  getSmartLoopPid,
  readCycleLockMeta,
} from '@/lib/loop'

export const dynamic = 'force-dynamic'

export async function GET() {
  const state = getLoopState()
  const config = getLoopConfig()
  const lockHeld = isCycleLockHeld()
  const lockMeta = readCycleLockMeta()
  const smartLoopRunning = isSmartLoopRunning()
  const smartLoopPid = getSmartLoopPid()

  return NextResponse.json({
    state: { ...state, lockHeld, smartLoopPid: smartLoopPid ?? state.smartLoopPid },
    config,
    lock: { held: lockHeld, meta: lockMeta },
    smartLoop: {
      running: smartLoopRunning,
      pid: smartLoopPid,
      logFile: '/tmp/smart-loop.log',
    },
  })
}
