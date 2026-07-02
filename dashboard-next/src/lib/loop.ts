import { readFileSync, writeFileSync, existsSync } from 'fs'
import { join } from 'path'

export const PROJECT_ROOT = join(process.cwd(), '..')
export const LOOP_CONFIG_FILE = join(PROJECT_ROOT, 'data', 'loop-config.json')
export const LOOP_STATE_FILE = join(PROJECT_ROOT, 'data', 'loop-state.json')
export const CYCLE_LOCK_META = '/tmp/clawd-cycle.meta.json'
export const SMART_LOOP_PID_FILE = '/tmp/clawd-smart-loop.pid'

const DEFAULT_LOOP_CONFIG = {
  intervalSeconds: 900,
  minIntervalSeconds: 300,
  maxIntervalSeconds: 1800,
  phases: ['preflight', 'analysis', 'decision', 'execution', 'recovery', 'observability'],
  accelerateOnPendingRecs: true,
  accelerateOnErrors: true,
  writeMemorySummary: true,
  rateLimitBackoffSeconds: 60,
}

export interface LoopPhaseResult {
  name: string
  status: string
  startedAt?: string
  completedAt?: string
  exitCode?: number
}

export interface LoopState {
  cycleId: string | null
  cycleNumber: number
  startedAt: string | null
  completedAt: string | null
  phases: LoopPhaseResult[]
  nextRunAt: string | null
  intervalUsed: number
  errors: Array<{ phase?: string; message?: string }>
  summary: string
  lockHeld: boolean
  smartLoopPid: number | null
  rateLimited?: boolean
}

function isPidAlive(pid: number): boolean {
  try {
    process.kill(pid, 0)
    return true
  } catch {
    return false
  }
}

export function getLoopConfig() {
  try {
    if (existsSync(LOOP_CONFIG_FILE)) {
      return { ...DEFAULT_LOOP_CONFIG, ...JSON.parse(readFileSync(LOOP_CONFIG_FILE, 'utf-8')) }
    }
  } catch {
    // fall through
  }
  return DEFAULT_LOOP_CONFIG
}

export function saveLoopConfig(body: Record<string, unknown>) {
  const updated = { ...getLoopConfig(), ...body }
  writeFileSync(LOOP_CONFIG_FILE, JSON.stringify(updated, null, 2))
  return updated
}

export function getLoopState(): LoopState {
  try {
    if (existsSync(LOOP_STATE_FILE)) {
      return JSON.parse(readFileSync(LOOP_STATE_FILE, 'utf-8')) as LoopState
    }
  } catch {
    // fall through
  }
  return {
    cycleId: null,
    cycleNumber: 0,
    startedAt: null,
    completedAt: null,
    phases: [],
    nextRunAt: null,
    intervalUsed: 900,
    errors: [],
    summary: 'Aguardando primeiro ciclo.',
    lockHeld: false,
    smartLoopPid: null,
  }
}

export function readCycleLockMeta(): Record<string, unknown> {
  try {
    if (existsSync(CYCLE_LOCK_META)) {
      return JSON.parse(readFileSync(CYCLE_LOCK_META, 'utf-8'))
    }
  } catch {
    // fall through
  }
  return {}
}

export function isCycleLockHeld(): boolean {
  if (!existsSync(CYCLE_LOCK_META)) return false
  const meta = readCycleLockMeta()
  const pid = meta.pid as number | undefined
  if (!pid) return true
  return isPidAlive(pid)
}

export function getSmartLoopPid(): number | null {
  try {
    if (existsSync(SMART_LOOP_PID_FILE)) {
      const pid = parseInt(readFileSync(SMART_LOOP_PID_FILE, 'utf-8').trim(), 10)
      if (!Number.isNaN(pid) && isPidAlive(pid)) {
        return pid
      }
    }
  } catch {
    // fall through
  }
  return null
}

export function isSmartLoopRunning(): boolean {
  return getSmartLoopPid() !== null
}

export function generateCycleId(): string {
  return `cycle-${new Date().toISOString().replace(/[:.]/g, '').slice(0, 15)}Z`
}
