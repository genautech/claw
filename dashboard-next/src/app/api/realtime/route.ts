import { NextResponse } from 'next/server'
import { readFileSync, existsSync, statSync } from 'fs'
import { join } from 'path'
import { execFile } from 'child_process'
import { promisify } from 'util'
import { getLoopState, isCycleLockHeld, isSmartLoopRunning, getSmartLoopPid } from '@/lib/loop'
import { getRegistryEntry } from '@/lib/agentRegistry'

const execFileAsync = promisify(execFile)

export const dynamic = 'force-dynamic'

const DATA_DIR = join(process.cwd(), '..', 'data')
const EXECUTOR_URL = process.env.EXECUTOR_URL || 'http://127.0.0.1:8789'
const NINJA_FILE = join(DATA_DIR, 'ninja_trades.jsonl')

function parseLastJsonlLine(path: string): Record<string, unknown> | null {
  if (!existsSync(path)) return null
  try {
    const lines = readFileSync(path, 'utf-8').trim().split('\n').filter(Boolean)
    if (!lines.length) return null
    return JSON.parse(lines[lines.length - 1]) as Record<string, unknown>
  } catch {
    return null
  }
}

async function executorHealth() {
  try {
    const res = await fetch(`${EXECUTOR_URL}/health`, { signal: AbortSignal.timeout(2500) })
    if (!res.ok) return { online: false, offline: true }
    return { ...(await res.json()), online: true, offline: false }
  } catch {
    return { online: false, offline: true }
  }
}

async function isNinjaAgentRunning(): Promise<boolean> {
  if (getRegistryEntry('ArbitrageNinja') !== null) return true
  try {
    const { stdout } = await execFileAsync('pgrep', ['-f', 'agent_ninja_arbitrage.py'])
    return stdout.trim().length > 0
  } catch {
    return false
  }
}

export async function GET() {
  const [health, loopState, ninjaAgentRunning] = await Promise.all([
    executorHealth(),
    Promise.resolve(getLoopState()),
    isNinjaAgentRunning(),
  ])

  const ninjaLast = parseLastJsonlLine(NINJA_FILE)
  const ninjaMtime = existsSync(NINJA_FILE) ? statSync(NINJA_FILE).mtimeMs : null

  return NextResponse.json({
    ts: new Date().toISOString(),
    executor: health,
    loop: { ...loopState, lockHeld: isCycleLockHeld() },
    smartLoop: {
      running: isSmartLoopRunning(),
      pid: getSmartLoopPid(),
    },
    ninja: {
      lastTrade: ninjaLast,
      fileMtime: ninjaMtime,
    },
    ninjaAgentRunning,
  })
}
