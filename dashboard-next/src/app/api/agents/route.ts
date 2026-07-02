import { NextResponse } from 'next/server'
import { statSync, existsSync } from 'fs'
import { join } from 'path'
import { execFile } from 'child_process'
import { promisify } from 'util'
import { spawnBackground } from '@/lib/spawnBackground'
import {
  getRegistryEntry,
  setRegistryEntry,
  removeRegistryEntry,
  isPidAlive,
} from '@/lib/agentRegistry'
import { getCached } from '@/lib/dataCache'

const execFileAsync = promisify(execFile)
const PROJECT_ROOT = join(process.cwd(), '..')

type AgentMode = 'daemon' | 'cycle'
type AgentStatus = 'active' | 'idle' | 'recent' | 'offline'

interface AgentDef {
  script: string
  args: string[]
  logName: string
  mode: AgentMode
  processPattern?: string
  reportPath?: string
  recentWindowMs?: number
  useShell?: boolean
  spawnCommand?: string
  spawnArgs?: string[]
}

interface AgentInfo {
  status: AgentStatus
  mode: AgentMode
  lastRun: string | null
  pid?: number | null
}

const AGENT_MAP: Record<string, AgentDef> = {
  PolyClaw: { script: 'scripts/agent_polyclaw.py', args: [], logName: 'polyclaw', mode: 'cycle', recentWindowMs: 900000 },
  PolyWhale: { script: 'scripts/agent_polywhale.py', args: [], logName: 'polywhale', mode: 'cycle', recentWindowMs: 900000 },
  Polybot: { script: 'scripts/agent_polybot_analyzer.py', args: ['--all'], logName: 'polybot', mode: 'cycle', recentWindowMs: 900000 },
  Brimo: { script: 'scripts/brimo.py', args: ['--monitor'], logName: 'brimo', mode: 'daemon', processPattern: 'brimo.py --monitor' },
  CorrectionAgent: { script: 'scripts/correction_agent.py', args: [], logName: 'correctionagent', mode: 'daemon', processPattern: 'correction_agent.py' },
  AutoCorrect: { script: 'scripts/agent_autocorrect.py', args: ['--scan', '--propose'], logName: 'autocorrect', mode: 'cycle', recentWindowMs: 900000 },
  Executor: { script: 'scripts/start-executor.sh', args: [], logName: 'executor', mode: 'daemon', processPattern: 'polymarket-exec.py --serve', useShell: true },
  ArbitrageNinja: {
    script: 'scripts/agent_ninja_arbitrage.py',
    args: ['--market', 'auto', '--daemon'],
    logName: 'ninja-agent',
    mode: 'daemon',
    processPattern: 'agent_ninja_arbitrage.py',
    useShell: false,
  },
  SmartLoop: {
    script: 'scripts/smart-loop.sh',
    args: [],
    logName: 'smart-loop',
    mode: 'daemon',
    processPattern: 'scripts/smart-loop.sh',
    useShell: true,
  },
  LatencyNinja: {
    script: 'scripts/run-agents.sh',
    args: ['ninja'],
    logName: 'latencyninja',
    mode: 'cycle',
    reportPath: 'logs/latency-report.json',
    recentWindowMs: 900000,
    useShell: true,
  },
}

function logPath(name: string) {
  return `/tmp/${name}.log`
}

function formatLastRun(mtimeMs: number | null): string | null {
  if (mtimeMs === null) return null
  return new Date(mtimeMs).toISOString()
}

function getLogMtime(logName: string): number | null {
  try {
    return statSync(logPath(logName)).mtimeMs
  } catch {
    return null
  }
}

async function isProcessRunning(pattern: string): Promise<boolean> {
  try {
    const { stdout } = await execFileAsync('pgrep', ['-f', pattern])
    return stdout.trim().length > 0
  } catch {
    return false
  }
}

async function buildAgentInfo(name: string, def: AgentDef): Promise<AgentInfo> {
  const registry = getRegistryEntry(name)
  if (registry && isPidAlive(registry.pid)) {
    return { status: 'active', mode: def.mode, lastRun: registry.startedAt, pid: registry.pid }
  }

  if (def.mode === 'daemon') {
    const pattern = def.processPattern || def.script
    const running = await isProcessRunning(pattern)
    if (name === 'Executor') {
      try {
        const res = await fetch('http://127.0.0.1:8789/health', { signal: AbortSignal.timeout(3000) })
        if (res.ok) {
          return { status: 'active', mode: 'daemon', lastRun: new Date().toISOString() }
        }
      } catch {
        // fall through
      }
    }
    const logMtime = getLogMtime(def.logName)
    return {
      status: running ? 'active' : 'offline',
      mode: 'daemon',
      lastRun: formatLastRun(logMtime),
    }
  }

  const windowMs = def.recentWindowMs ?? 900000
  let mtime: number | null = null

  if (def.reportPath) {
    const reportFile = join(PROJECT_ROOT, def.reportPath)
    if (existsSync(reportFile)) {
      try {
        mtime = statSync(reportFile).mtimeMs
      } catch {
        mtime = null
      }
    }
  } else {
    mtime = getLogMtime(def.logName)
  }

  if (mtime === null) {
    return { status: 'offline', mode: 'cycle', lastRun: null }
  }

  const age = Date.now() - mtime
  const status: AgentStatus = age < windowMs ? 'recent' : 'idle'
  return { status, mode: 'cycle', lastRun: formatLastRun(mtime) }
}

function toLegacyStatus(info: AgentInfo): string {
  if (info.status === 'active' || info.status === 'recent') return 'active'
  return 'offline'
}

async function findPidForPattern(pattern: string, delayMs: number): Promise<number | null> {
  await new Promise((r) => setTimeout(r, delayMs))
  try {
    const { stdout } = await execFileAsync('pgrep', ['-f', pattern])
    const pid = parseInt(stdout.trim().split('\n')[0], 10)
    return Number.isNaN(pid) ? null : pid
  } catch {
    return null
  }
}

export async function GET() {
  try {
    const payload = await getCached(
      'agents-status',
      async () => {
        const entries = await Promise.all(
          Object.entries(AGENT_MAP).map(async ([name, def]) => {
            const info = await buildAgentInfo(name, def)
            return [name, info] as const
          }),
        )
        const agents = Object.fromEntries(entries) as Record<string, AgentInfo>
        const statuses = Object.fromEntries(
          Object.entries(agents).map(([name, info]) => [name, toLegacyStatus(info)]),
        )
        return { agents, statuses }
      },
      { ttlMs: 5000 },
    )

    return NextResponse.json(payload)
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Unknown error'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}

export async function POST(request: Request) {
  try {
    const { agent, action } = await request.json()
    const def = AGENT_MAP[agent as string]

    if (!def) return NextResponse.json({ error: 'Unknown agent' }, { status: 400 })

    const logFile = logPath(def.logName)

    if (action === 'stop') {
      const entry = getRegistryEntry(agent as string)
      if (entry) {
        try {
          process.kill(entry.pid, 'SIGTERM')
        } catch {
          // process gone
        }
        removeRegistryEntry(agent as string)
      }
      const pattern = def.processPattern || def.script
      await execFileAsync('pkill', ['-f', pattern]).catch(() => {})
      return NextResponse.json({ success: true, status: 'offline' })
    }

    if (action === 'start') {
      const existing = getRegistryEntry(agent as string)
      if (existing) {
        return NextResponse.json({ success: true, status: 'active', pid: existing.pid, alreadyRunning: true })
      }

      if (def.mode === 'daemon') {
        const pattern = def.processPattern || def.script
        if (await isProcessRunning(pattern)) {
          return NextResponse.json({ success: true, status: 'active', alreadyRunning: true })
        }
      }

      if (agent === 'SmartLoop') {
        spawnBackground('bash', ['scripts/start-autoloop.sh'], logFile)
        return NextResponse.json({ success: true, status: 'active', message: 'Smart loop starting' })
      }

      if (def.useShell) {
        spawnBackground('bash', [def.script, ...def.args], logFile)
      } else {
        spawnBackground('python3', [def.script, ...def.args], logFile)
      }

      if (def.mode === 'daemon' && def.processPattern) {
        const pid = await findPidForPattern(def.processPattern, agent === 'ArbitrageNinja' ? 2000 : 1500)
        if (pid) {
          setRegistryEntry(agent as string, {
            agent: agent as string,
            pid,
            startedAt: new Date().toISOString(),
            command: def.useShell ? `bash ${def.script}` : `python3 ${def.script}`,
          })
          return NextResponse.json({ success: true, status: 'active', pid })
        }
      }

      return NextResponse.json({ success: true, status: def.mode === 'cycle' ? 'recent' : 'active' })
    }

    return NextResponse.json({ error: 'Invalid action' }, { status: 400 })
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Unknown error'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
